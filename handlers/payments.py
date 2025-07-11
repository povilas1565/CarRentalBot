from io import BytesIO
import qrcode
import datetime
import hashlib

from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile

from keyboards.inline import payment_confirmation_kb
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.booking import Booking, BookingStatus
from models.user import User
from database import SessionLocal

from config import FREEKASSA_MERCHANT_ID, FREEKASSA_SECRET_1, NBS_PRIMALAC, NBS_BROJ_RACUNA
from handlers.menu import main_menu_kb


class PaymentStates(StatesGroup):
    waiting_for_booking = State()
    waiting_for_method = State()


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
    return (
        f"https://pay.freekassa.ru/?m={FREEKASSA_MERCHANT_ID}&oa={amount}"
        f"&currency={currency}&o={order_id}&s={sign}"
    )


# ⬇️ Хендлер запуска через inline-кнопку
async def start_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы. Пожалуйста, используйте /start.", reply_markup=main_menu_kb())
            await state.finish()
            return

        bookings = db.query(Booking).filter(
            Booking.renter_id == user.id,
            Booking.status == BookingStatus.CONFIRMED
        ).all()

        if not bookings:
            await callback.message.edit_text("У вас нет бронирований, доступных для оплаты.", reply_markup=main_menu_kb())
            await state.finish()
            return

        keyboard = InlineKeyboardMarkup(row_width=1)
        for b in bookings:
            keyboard.add(InlineKeyboardButton(
                f"{b.car.model} с {b.date_from} по {b.date_to}",
                callback_data=f"pay_booking_{b.id}"
            ))
        keyboard.add(InlineKeyboardButton("Отмена", callback_data="cancel"))

        await callback.message.edit_text("Выберите бронирование для оплаты:", reply_markup=keyboard)
        await PaymentStates.waiting_for_booking.set()
        await callback.answer()
    finally:
        db.close()


# ⬇️ Выбор бронирования
async def select_booking_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await callback.message.edit_text("Оплата отменена.", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    if not callback.data.startswith("pay_booking_"):
        await callback.answer()
        return

    booking_id = int(callback.data.split("_")[-1])
    await state.update_data(selected_booking_id=booking_id)

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Оплата через FreeKassa", callback_data="method_freekassa"),
        InlineKeyboardButton("Оплата через NBS QR", callback_data="method_qr"),
        InlineKeyboardButton("Отмена", callback_data="cancel")
    )

    await callback.message.edit_text("Выберите способ оплаты:", reply_markup=keyboard)
    await PaymentStates.waiting_for_method.set()
    await callback.answer()


# ⬇️ Выбор способа оплаты
async def select_method_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await callback.message.edit_text("Оплата отменена.", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    data = await state.get_data()
    booking_id = data.get("selected_booking_id")

    db = SessionLocal()
    try:
        if callback.data == "method_freekassa":
            method = PaymentMethod.FREEKASSA
            payment, booking = create_payment(db, booking_id, method)
            url = create_freekassa_payment_link(booking, payment.id)

            keyboard = InlineKeyboardMarkup().add(
                InlineKeyboardButton("Перейти к оплате", url=url)
            )
            await callback.message.edit_text("Нажмите кнопку ниже для перехода к оплате:", reply_markup=keyboard)

            confirm_kb = payment_confirmation_kb(payment.id)
            await callback.message.answer(
                f"Платеж #{payment.id} на сумму {payment.amount:.2f} RUB. Подтвердите оплату или отмените.",
                reply_markup=confirm_kb
            )

        elif callback.data == "method_qr":
            method = PaymentMethod.NBS_QR
            payment, booking = create_payment(db, booking_id, method)
            qr_image = generate_nbs_qr(booking)

            photo = InputFile(qr_image, filename="qr.png")
            await callback.bot.send_photo(
                callback.from_user.id,
                photo=photo,
                caption=f"Отсканируйте QR-код для оплаты аренды {booking.car.model} с {booking.date_from} по {booking.date_to}.",
                reply_markup=main_menu_kb()
            )
            await callback.message.delete()

            confirm_kb = payment_confirmation_kb(payment.id)
            await callback.message.answer(
                f"Платеж #{payment.id} на сумму {payment.amount:.2f} EUR. Подтвердите оплату или отмените.",
                reply_markup=confirm_kb
            )

        else:
            await callback.answer()
            return
    finally:
        db.close()

    await state.finish()
    await callback.answer()


# ⬇️ Регистрация хендлеров
def register_payments_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(start_payment_handler, lambda c: c.data == "cmd_pay", state="*")
    dp.register_callback_query_handler(select_booking_handler, lambda c: c.data.startswith("pay_booking_") or c.data == "cancel", state=PaymentStates.waiting_for_booking)
    dp.register_callback_query_handler(select_method_handler, lambda c: c.data.startswith("method_") or c.data == "cancel", state=PaymentStates.waiting_for_method)

