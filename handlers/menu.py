from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import SessionLocal
from handlers import cars
from handlers.bookings import start_booking
from handlers.registration import start_registration
from handlers.contracts import start_contract, cancel_contract_callback  # импортируем контрактные функции
from models.payment import Payment, PaymentStatus


class MenuFSM(StatesGroup):
    waiting_for_confirmation = State()


def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📝 Регистрация", callback_data="cmd_register"),
        InlineKeyboardButton("🚗 Добавить автомобиль", callback_data="cmd_add_car"),
        InlineKeyboardButton("📋 Мои автомобили", callback_data="cmd_my_cars"),
        InlineKeyboardButton("📅 Забронировать авто", callback_data="cmd_book"),
        InlineKeyboardButton("📝 Оставить отзыв", callback_data="cmd_review"),
        InlineKeyboardButton("⭐️ Просмотреть отзывы", callback_data="cmd_reviews"),
        InlineKeyboardButton("📄 Договоры", callback_data="submenu_contracts"),
        InlineKeyboardButton("💳 Оплата", callback_data="submenu_payments"),
    )
    return kb


def contracts_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 Создать / получить договор", callback_data="cmd_contract"),
        InlineKeyboardButton("❌ Аннулировать договор", callback_data="cmd_cancel_contract"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb


def payments_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить бронирование", callback_data="cmd_pay"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb


async def process_menu_callbacks(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "cmd_register":
        await callback.message.delete()
        await start_registration(callback.message, state)
        await callback.answer()
        return

    if data == "cmd_book":
        await callback.message.delete()
        await start_booking(callback.message, state)
        await callback.answer()
        return

    if data == "cmd_contract":
        await callback.message.delete()
        await start_contract(callback.message, state)
        await callback.answer()
        return

    if data == "cmd_cancel_contract":
        await callback.message.delete()
        await cancel_contract_callback(callback, state)
        await callback.answer()
        return

    if data == "back_main":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    if data == "submenu_contracts":
        await callback.message.edit_text("Меню договоров:", reply_markup=contracts_menu_kb())
        await callback.answer()
        return

    if data == "submenu_payments":
        await callback.message.edit_text("Меню оплат:", reply_markup=payments_menu_kb())
        await callback.answer()
        return

    # Новый код: вызываем функции из cars.py напрямую
    if data == "cmd_add_car":
        await callback.message.delete()
        await cars.add_car_start(callback.message, state)  # Запускаем FSM добавления авто
        await callback.answer()
        return

    if data == "cmd_my_cars":
        await callback.message.delete()
        await cars.list_user_cars(callback.message, state)  # Показываем список авто пользователя
        await callback.answer()
        return

    await callback.answer("Неизвестная команда.", show_alert=True)


async def confirmation_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data.startswith("pay_confirm_"):
        payment_id = int(data.split("_")[-1])
        await callback.message.edit_text("Обрабатываем оплату...")
        await process_payment(callback, payment_id)
        await state.finish()

    elif data == "pay_decline":
        await callback.message.edit_text("Оплата отменена.", reply_markup=main_menu_kb())
        await state.finish()

    elif data.startswith("pay_cancel_confirm_"):
        payment_id = int(data.split("_")[-1])
        await callback.message.edit_text("Обрабатываем отмену оплаты...")
        await process_payment_cancellation(callback, payment_id)
        await state.finish()

    elif data == "pay_cancel_decline":
        await callback.message.edit_text("Отмена оплаты отменена.", reply_markup=main_menu_kb())
        await state.finish()

    else:
        await callback.answer()


async def process_payment(callback: types.CallbackQuery, payment_id: int):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            await callback.message.edit_text("Платеж не найден.", reply_markup=main_menu_kb())
            return
        if payment.status == PaymentStatus.COMPLETED:
            await callback.message.edit_text("Платеж уже оплачен.", reply_markup=main_menu_kb())
            return

        payment.status = PaymentStatus.COMPLETED
        db.commit()
        await callback.message.edit_text("Оплата успешно подтверждена!", reply_markup=main_menu_kb())
    finally:
        db.close()
    await callback.answer()


async def process_payment_cancellation(callback: types.CallbackQuery, payment_id: int):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            await callback.message.edit_text("Платеж не найден.", reply_markup=main_menu_kb())
            return
        if payment.status == PaymentStatus.CANCELLED:
            await callback.message.edit_text("Платеж уже отменён.", reply_markup=main_menu_kb())
            return

        payment.status = PaymentStatus.CANCELLED
        db.commit()
        await callback.message.edit_text("Оплата успешно отменена.", reply_markup=main_menu_kb())
    finally:
        db.close()
    await callback.answer()

async def start_command(message: types.Message):
    await message.answer("Добро пожаловать! Главное меню:", reply_markup=main_menu_kb())


async def menu_command(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


def register_menu_handlers(dp: Dispatcher):
    dp.register_message_handler(start_command, commands=["start"], state="*")
    dp.register_message_handler(menu_command, commands=["menu"], state="*")
    dp.register_callback_query_handler(process_menu_callbacks, state="*")
    dp.register_callback_query_handler(confirmation_handler, state=MenuFSM.waiting_for_confirmation)