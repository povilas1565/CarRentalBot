from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func

from database import SessionLocal
from handlers import cars
from handlers.bookings import start_booking
from handlers.registration import start_registration
from handlers.contracts import start_contract, cancel_contract_callback
from models.car import Car
from models.payment import Payment, PaymentStatus
from models.user import User

# FSM для подтверждений
class MenuFSM(StatesGroup):
    waiting_for_confirmation = State()


# Главное меню
def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚘 Каталог автомобилей", callback_data="cmd_catalog"),
        InlineKeyboardButton("📅 Забронировать авто", callback_data="cmd_book"),
        InlineKeyboardButton("🚗 Сдать авто в аренду", callback_data="cmd_add_car"),
        InlineKeyboardButton("📋 Мои автомобили", callback_data="cmd_my_cars"),
        InlineKeyboardButton("📄 Договоры", callback_data="submenu_contracts"),
        InlineKeyboardButton("💳 Оплата", callback_data="submenu_payments"),
        InlineKeyboardButton("📝 Оставить отзыв", callback_data="cmd_review"),
        InlineKeyboardButton("⭐️ Просмотреть отзывы", callback_data="cmd_reviews"),
    )
    return kb


# Меню договоров
def contracts_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 Создать / получить договор", callback_data="cmd_contract"),
        InlineKeyboardButton("❌ Аннулировать договор", callback_data="cmd_cancel_contract"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb


# Меню оплат
def payments_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить бронирование", callback_data="cmd_pay"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_main"),
    )
    return kb


# Проверка регистрации пользователя
async def require_registration(message: types.Message):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id, User.registered == True).first()
        return user is not None
    finally:
        db.close()


# Обработка всех callback из меню
async def process_menu_callbacks(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "cmd_catalog":
        await callback.message.delete()
        await show_catalog(callback.message)
        await callback.answer()
        return
    
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

    if data == "cmd_add_car":
        if not await require_registration(callback.message):
            await callback.message.answer("⚠️ Для сдачи автомобиля необходимо зарегистрироваться.")
            await start_registration(callback.message, state)
            return
        await callback.message.delete()
        await cars.add_car_start(callback.message, state)
        await callback.answer()
        return

    if data == "cmd_my_cars":
        if not await require_registration(callback.message):
            await callback.message.answer("⚠️ Для просмотра своих авто необходимо зарегистрироваться.")
            await start_registration(callback.message, state)
            return
        await callback.message.delete()
        await cars.list_user_cars(callback.message, state)
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

    await callback.answer("Неизвестная команда.", show_alert=True)


# Подтверждение оплаты или отмены
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


# Показ каталога автомобилей
async def show_catalog(message: types.Message):
    db = SessionLocal()
    cars_list = db.query(Car).all()
    db.close()

    if not cars_list:
        await message.answer("В каталоге нет автомобилей.", reply_markup=main_menu_kb())
        return

    msg = "🚗 Каталог автомобилей:\n\n"
    for car in cars_list:
        msg += f"ID: {car.id} | {car.model} | Цена: {car.price_per_day:.2f} EUR/день\n"
    await message.answer(msg, reply_markup=main_menu_kb())


# Обработка оплаты
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


# Отмена оплаты
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


# Команды /start и /menu
async def start_command(message: types.Message):
    await message.answer("Добро пожаловать! Главное меню:", reply_markup=main_menu_kb())


async def menu_command(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


# Регистрация хендлеров
def register_menu_handlers(dp: Dispatcher):
     dp.register_message_handler(start_command, commands=["start"], state="*")
     dp.register_message_handler(menu_command, commands=["menu"], state="*")
     dp.register_callback_query_handler(process_menu_callbacks, state="*")
     # Ловим только кнопки оплат из инлайнов
     dp.register_callback_query_handler(
        confirmation_handler,
        lambda c: c.data.startswith("pay_confirm_")
                  or c.data == "pay_decline"
                  or c.data.startswith("pay_cancel_confirm_")
                  or c.data == "pay_cancel_decline",
        state="*"
    )
