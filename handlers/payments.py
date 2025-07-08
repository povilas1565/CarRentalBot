from io import BytesIO
import qrcode
import datetime

from aiogram import types, Dispatcher
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import TelegramAPIError

from models.payment import Payment, PaymentStatus, PaymentMethod
from models.booking import Booking, BookingStatus
from database import SessionLocal

from loguru import logger

from config import (
    FREEKASSA_MERCHANT_ID,
    FREEKASSA_SECRET_1,
    NBS_PRIMALAC,
    NBS_BROJ_RACUNA
)
import hashlib

def create_payment(db, booking_id: int, method: PaymentMethod):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise Exception("Booking not found")

    payment = Payment(
        booking_id=booking.id,
        amount=booking.total_price,
        status=PaymentStatus.PENDING,
        method=method,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment, booking


def generate_nbs_qr(booking: Booking):
    svrha = f"Аренда авто {booking.car.model} {booking.date_from}–{booking.date_to}"
    iznos = f"{booking.total_price:.2f}"

    qr_text = f"ST01|{NBS_PRIMALAC}|{svrha}|{iznos}|{NBS_BROJ_RACUNA}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def create_freekassa_payment_link(booking: Booking, payment_id: int):
    amount = f"{booking.total_price:.2f}"
    currency = "EUR"
    order_id = str(payment_id)

    sign_str = f"{FREEKASSA_MERCHANT_ID}:{amount}:{FREEKASSA_SECRET_1}:{currency}:{order_id}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    url = (
        f"https://pay.freekassa.ru/"
        f"?m={FREEKASSA_MERCHANT_ID}"
        f"&oa={amount}"
        f"&currency={currency}"
        f"&o={order_id}"
        f"&s={sign}"
    )
    return url
def handle_payment_choice(db, booking_id: int, method: PaymentMethod):
    payment, booking = create_payment(db, booking_id, method)

    if method == PaymentMethod.NBS_QR:
        qr_image = generate_nbs_qr(booking)
        return {
            "type": "qr",
            "qr_image": qr_image,
            "description": f"Отсканируйте QR-код для оплаты аренды {booking.car.model} с {booking.date_from} по {booking.date_to}."
        }

    elif method == PaymentMethod.FREEKASSA:
        url = create_freekassa_payment_link(booking, payment.id)
        return {"type": "link", "url": url}

    else:
        raise Exception("Неизвестный метод оплаты")


async def send_payment_to_user(bot, chat_id: int, payment_result: dict):
    try:
        if payment_result["type"] == "qr":
            qr_image: BytesIO = payment_result["qr_image"]
            caption = payment_result.get("description", "Отсканируйте QR-код для оплаты")
            qr_image.seek(0)
            await bot.send_photo(chat_id, photo=InputFile(qr_image, filename="payment_qr.png"), caption=caption)

        elif payment_result["type"] == "link":
            url = payment_result["url"]
            text = f"Перейдите по ссылке для оплаты:\n{url}"
            await bot.send_message(chat_id, text)

        else:
            await bot.send_message(chat_id, "Ошибка: неизвестный формат оплаты.")
    except TelegramAPIError as e:
        logger.error(f"Telegram API Error: {e}")


# --- Хендлеры с кнопками ---

async def start_pay_process(message: types.Message):
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        bookings = db.query(Booking).filter(
            Booking.renter.has(telegram_id=user_id),
            Booking.status == BookingStatus.CONFIRMED
        ).all()

        if not bookings:
            await message.answer("У вас нет бронирований для оплаты.")
            return

        keyboard = InlineKeyboardMarkup(row_width=1)
        for b in bookings:
            btn_text = f"Бронь #{b.id} - {b.car.model} с {b.date_from} по {b.date_to} ({b.total_price} EUR)"
            keyboard.insert(InlineKeyboardButton(btn_text, callback_data=f"pay_select_booking:{b.id}"))

        await message.answer("Выберите бронирование для оплаты:", reply_markup=keyboard)
    finally:
        db.close()


async def callback_select_booking(callback: types.CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    keyboard = InlineKeyboardMarkup(row_width=1)

    # Показываем только актуальные методы оплаты
    keyboard.insert(InlineKeyboardButton("FreeKassa", callback_data=f"pay_select_method:{booking_id}:freekassa"))
    keyboard.insert(InlineKeyboardButton("NBS QR", callback_data=f"pay_select_method:{booking_id}:nbs_qr"))

    await callback.message.edit_text("Выберите метод оплаты:", reply_markup=keyboard)
    await callback.answer()


async def callback_select_method(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    booking_id = int(parts[1])
    method_str = parts[2]
    method = PaymentMethod(method_str)

    db = SessionLocal()
    try:
        payment_result = handle_payment_choice(db, booking_id, method)
    except Exception as e:
        await callback.message.answer(f"Ошибка при создании платежа: {e}")
        await callback.answer()
        db.close()
        return
    db.close()

    await send_payment_to_user(callback.bot, callback.message.chat.id, payment_result)
    await callback.answer("Платеж создан!")


async def pay_cancel_handler(message: types.Message):
    db = SessionLocal()
    try:
        user_id = message.from_user.id
        booking = (
            db.query(Booking)
            .filter(Booking.renter.has(telegram_id=user_id))
            .filter(Booking.status == BookingStatus.PENDING)
            .order_by(Booking.date_from.desc())
            .first()
        )
        if not booking:
            await message.answer("Нет активных оплат для отмены.")
            return

        booking.status = BookingStatus.CANCELLED
        db.commit()
        await message.answer(f"Оплата бронирования #{booking.id} отменена.")
        logger.info(f"User {user_id} cancelled payment for booking {booking.id}")
    except Exception as e:
        logger.error(f"Ошибка отмены оплаты: {e}")
        await message.answer("Ошибка при отмене оплаты. Попробуйте позже.")
    finally:
        db.close()


def register_payments_handlers(dp: Dispatcher):
    dp.register_message_handler(start_pay_process, commands=["pay"])
    dp.register_callback_query_handler(callback_select_booking, lambda c: c.data and c.data.startswith("pay_select_booking:"))
    dp.register_callback_query_handler(callback_select_method, lambda c: c.data and c.data.startswith("pay_select_method:"))
    dp.register_message_handler(pay_cancel_handler, commands=["pay_cancel"])