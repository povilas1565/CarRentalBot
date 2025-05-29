import qrcode
from io import BytesIO
import stripe
import hashlib
import datetime

from aiogram import types, Dispatcher
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Command
from aiogram.utils.exceptions import TelegramAPIError

from models.payment import Payment, PaymentStatus, PaymentMethod
from models.booking import Booking, BookingStatus
from database import SessionLocal

# Инициализация Stripe
stripe.api_key = "YOUR_STRIPE_SECRET_KEY"

# Freekassa настройки (замени на свои)
FREEKASSA_MERCHANT_ID = "your_merchant_id"
FREEKASSA_SECRET_1 = "your_secret_1"
FREEKASSA_SECRET_2 = "your_secret_2"
FREEKASSA_PAY_URL = "https://pay.freekassa.ru/"

# NBS QR данные
NBS_PRIMALAC = "ROMAN DAVYDOV PR"
NBS_BROJ_RACUNA = "190-0000000034540-60"


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

    qr_text = (
        f"ST01|{NBS_PRIMALAC}|{svrha}|{iznos}|{NBS_BROJ_RACUNA}"
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")

    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


def create_stripe_payment_link(booking: Booking):
    try:
        payment_link = stripe.PaymentLink.create(
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "product_data": {
                        "name": f"Аренда {booking.car.model} {booking.date_from}–{booking.date_to}",
                    },
                    "unit_amount": int(booking.total_price * 100),
                },
                "quantity": 1,
            }],
            after_completion={"type": "redirect", "redirect": {"url": "https://myrentcar.rs/thankyou"}},
        )
        return payment_link.url
    except Exception as e:
        print(f"Stripe error: {e}")
        return None


def create_freekassa_payment_link(booking: Booking, payment_id: int):
    out_summ = f"{booking.total_price:.2f}"
    inv_id = str(payment_id)
    crc_str = f"{FREEKASSA_MERCHANT_ID}:{out_summ}:{inv_id}:{FREEKASSA_SECRET_1}"
    signature = hashlib.md5(crc_str.encode("utf-8")).hexdigest()

    pay_url = (
        f"{FREEKASSA_PAY_URL}?m={FREEKASSA_MERCHANT_ID}"
        f"&oa={out_summ}&o={inv_id}&s={signature}"
        f"&us_phone=1&us_email=1&us_fio=1&us_address=1"
    )
    return pay_url


def handle_payment_choice(db, booking_id: int, method: PaymentMethod):
    payment, booking = create_payment(db, booking_id, method)

    if method == PaymentMethod.NBS_QR:
        qr_image = generate_nbs_qr(booking)
        return {
            "type": "qr",
            "qr_image": qr_image,
            "description": f"Отсканируйте QR-код для оплаты аренды {booking.car.model} с {booking.date_from} по {booking.date_to}."
        }

    elif method == PaymentMethod.STRIPE:
        url = create_stripe_payment_link(booking)
        if not url:
            raise Exception("Не удалось создать ссылку Stripe")
        return {"type": "link", "url": url}

    elif method == PaymentMethod.FREKASSA:
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
        print(f"Telegram API Error: {e}")


# --- Хендлеры с кнопками ---

async def start_pay_process(message: types.Message):
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        # Берём все бронирования пользователя, которые можно оплатить
        bookings = db.query(Booking).filter(
            Booking.renter_id == user_id,
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

    for method in PaymentMethod:
        keyboard.insert(InlineKeyboardButton(method.value.upper(), callback_data=f"pay_select_method:{booking_id}:{method.value}"))

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


def register_payments_handlers(dp: Dispatcher):
    dp.register_message_handler(start_pay_process, commands=["pay"])
    dp.register_callback_query_handler(callback_select_booking, lambda c: c.data and c.data.startswith("pay_select_booking:"))
    dp.register_callback_query_handler(callback_select_method, lambda c: c.data and c.data.startswith("pay_select_method:"))