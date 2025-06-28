import os
from jinja2 import Environment, FileSystemLoader
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from database import SessionLocal
from models.booking import Booking
from models.contract import Contract
from models.user import User
from loguru import logger

# Инициализация jinja2 шаблонов
env = Environment(loader=FileSystemLoader('templates'))

class ContractStates(StatesGroup):
    SELECT_BOOKING = State()
    CONFIRM_SIGNATURE = State()

async def start_contract(message: types.Message, state: FSMContext):
    db = SessionLocal()
    try:
        telegram_id = message.from_user.id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            await state.finish()
            return

        bookings = db.query(Booking).filter(Booking.renter_id == user.id, Booking.status == "confirmed").all()
        if not bookings:
            await message.answer("У вас нет активных бронирований для создания контракта.")
            await state.finish()
            return

        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for b in bookings:
            keyboard.add(KeyboardButton(f"Бронирование #{b.id} с {b.date_from} по {b.date_to}"))
        keyboard.add(KeyboardButton("Отмена"))

        bookings_map = {f"Бронирование #{b.id} с {b.date_from} по {b.date_to}": b.id for b in bookings}
        await state.update_data(bookings_map=bookings_map)

        await message.answer("Выберите бронирование для создания контракта:", reply_markup=keyboard)
        await ContractStates.SELECT_BOOKING.set()
    finally:
        db.close()

async def select_booking(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        await state.finish()
        return

    data = await state.get_data()
    bookings_map = data.get('bookings_map', {})
    if message.text not in bookings_map:
        await message.answer("Пожалуйста, выберите бронирование из списка.")
        return

    booking_id = bookings_map[message.text]
    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            await message.answer("Ошибка: бронирование не найдено.")
            await state.finish()
            return

        # Генерация контракта из шаблона
        template = env.get_template("contract_template.html")
        contract_text = template.render(
            booking=booking,
            user=booking.user,
            car=booking.car
        )
        os.makedirs("contracts", exist_ok=True)
        contract_path = f"contracts/contract_{booking.id}.html"
        with open(contract_path, "w", encoding="utf-8") as f:
            f.write(contract_text)

        await state.update_data(contract_path=contract_path, selected_booking_id=booking.id)

        new_contract = Contract(
            booking_id=booking.id,
            contract_pdf_path=contract_path,
            signed=False
        )
        db.add(new_contract)
        db.commit()

        # Спрашиваем о подписании
        keyboard = ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True
        ).add(KeyboardButton("да"), KeyboardButton("нет"))

        await message.answer("Контракт сгенерирован. Хотите подписать контракт? (да/нет)", reply_markup=keyboard)
        await ContractStates.CONFIRM_SIGNATURE.set()
    finally:
        db.close()

async def confirm_signature(message: types.Message, state: FSMContext):
    answer = message.text.lower()
    if answer not in ("да", "нет"):
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.")
        return

    if answer == "нет":
        await message.answer("Подписание контракта отменено.", reply_markup=ReplyKeyboardRemove())
        await state.finish()
        return

    data = await state.get_data()
    booking_id = data.get('selected_booking_id')
    if not booking_id:
        await message.answer("Ошибка: данные бронирования отсутствуют.")
        await state.finish()
        return

    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            await message.answer("Ошибка: бронирование не найдено.")
            await state.finish()
            return

        # Обновляем поле contract_signed, предполагается, что оно есть в модели Booking
        booking.contract_signed = True

        contract = db.query(Contract).filter(Contract.booking_id == booking.id).first()
        if contract:
            contract.signed = True

        db.commit()

        await message.answer("Контракт подписан успешно!", reply_markup=ReplyKeyboardRemove())
        logger.info(f"User {booking.user_id} подписал контракт по бронированию {booking.id}")
    finally:
        db.close()

    await state.finish()

async def cancel_contract(message: types.Message, state: FSMContext):
    await message.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    await state.finish()

def register_contracts_handlers(dp: Dispatcher):
    dp.register_message_handler(start_contract, commands=["contract"], state="*")
    dp.register_message_handler(select_booking, state=ContractStates.SELECT_BOOKING)
    dp.register_message_handler(confirm_signature, state=ContractStates.CONFIRM_SIGNATURE)
    dp.register_message_handler(cancel_contract, commands=["cancel_contract"], state="*")