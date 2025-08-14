import os
from jinja2 import Environment, FileSystemLoader
from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import joinedload

from database import SessionLocal
from models.booking import Booking
from models.contract import Contract
from models.user import User
from loguru import logger

# Jinja2 шаблоны
env = Environment(loader=FileSystemLoader('templates'))


class ContractStates(StatesGroup):
    SELECT_BOOKING = State()
    CONFIRM_SIGNATURE = State()
    AWAITING_CANCEL_SELECTION = State()


# Inline-кнопки для выбора бронирования
def booking_selection_kb(bookings):
    keyboard = InlineKeyboardMarkup(row_width=1)
    for booking in bookings:
        text = f"#{booking.id} | {booking.date_from} – {booking.date_to}"
        keyboard.add(InlineKeyboardButton(text, callback_data=f"select_booking_{booking.id}"))
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_contract"))
    return keyboard


# Кнопки подтверждения подписи
def confirm_signature_kb():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да", callback_data="sign_yes"),
        InlineKeyboardButton("❌ Нет", callback_data="sign_no")
    )
    keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_contract"))
    return keyboard


# Старт создания контракта
async def start_contract(message: types.Message, state: FSMContext):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
            await state.finish()
            return

        bookings = db.query(Booking).filter(
            Booking.renter_id == user.id,
            Booking.status == "confirmed"
        ).all()

        if not bookings:
            await message.answer("У вас нет активных бронирований.")
            await state.finish()
            return

        await state.update_data(bookings_map={b.id: b for b in bookings})
        await message.answer(
            "Выберите бронирование для создания контракта:",
            reply_markup=booking_selection_kb(bookings)
        )
        await ContractStates.SELECT_BOOKING.set()
    finally:
        db.close()


# Выбор бронирования
async def select_booking_callback(callback: types.CallbackQuery, state: FSMContext):
    booking_id_str = callback.data.replace("select_booking_", "")
    if not booking_id_str.isdigit():
        await callback.answer("Неверный формат.")
        return

    booking_id = int(booking_id_str)
    data = await state.get_data()
    bookings_map = data.get("bookings_map", {})
    booking = bookings_map.get(booking_id)
    if not booking:
        await callback.answer("Бронирование не найдено.")
        return

    db = SessionLocal()
    try:
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

        new_contract = Contract(
            booking_id=booking.id,
            contract_pdf_path=contract_path,
            signed=False
        )
        db.add(new_contract)
        db.commit()

        await state.update_data(selected_booking_id=booking.id, contract_path=contract_path)
        await callback.message.edit_text(
            "Контракт сгенерирован. Подписать контракт?",
            reply_markup=confirm_signature_kb()
        )
        await ContractStates.CONFIRM_SIGNATURE.set()
    except Exception as e:
        logger.error(f"Ошибка при генерации контракта: {e}")
        await callback.message.edit_text("Произошла ошибка при генерации контракта.")
        await state.finish()
    finally:
        db.close()
        await callback.answer()


# Подтверждение подписи
async def confirm_signature_callback(callback: types.CallbackQuery, state: FSMContext):
    from handlers.menu import main_menu_kb

    if callback.data in ["sign_no", "cancel_contract"]:
        await callback.message.edit_text("Операция отменена.", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    if callback.data != "sign_yes":
        await callback.answer()
        return

    data = await state.get_data()
    booking_id = data.get("selected_booking_id")
    if not booking_id:
        await callback.message.edit_text("Ошибка: данные бронирования не найдены.")
        await state.finish()
        await callback.answer()
        return

    db = SessionLocal()
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            await callback.message.edit_text("Бронирование не найдено.")
            await state.finish()
            return

        booking.contract_signed = True
        contract = db.query(Contract).filter(Contract.booking_id == booking.id).first()
        if contract:
            contract.signed = True

        db.commit()
        await callback.message.edit_text("✅ Контракт подписан успешно!", reply_markup=main_menu_kb())
        logger.info(f"User {booking.renter_id} подписал контракт #{booking.id}")
    except Exception as e:
        logger.error(f"Ошибка при подписании контракта: {e}")
        await callback.message.edit_text("Произошла ошибка при подписании контракта.")
    finally:
        db.close()
        await state.finish()
        await callback.answer()


# Отмена контракта или аннулирование
async def cancel_contract_callback(callback: types.CallbackQuery, state: FSMContext):
    from handlers.menu import main_menu_kb
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы.")
            return

        contracts = db.query(Contract).join(Booking).options(joinedload(Contract.booking)) \
            .filter(Booking.renter_id == user.id, Contract.signed == True).all()

        if not contracts:
            await callback.message.edit_text(
                "У вас нет подписанных договоров для аннулирования.",
                reply_markup=main_menu_kb()
            )
            return

        kb = InlineKeyboardMarkup(row_width=1)
        for contract in contracts:
            booking = contract.booking
            kb.add(InlineKeyboardButton(
                f"#{booking.id} от {booking.date_from} до {booking.date_to}",
                callback_data=f"cancel_contract_{contract.id}"
            ))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="cancel_contract_back"))

        await callback.message.edit_text("Выберите договор для аннулирования:", reply_markup=kb)
        await ContractStates.AWAITING_CANCEL_SELECTION.set()
    except Exception as e:
        logger.error(f"Ошибка при показе аннулирования: {e}")
        await callback.message.edit_text("Ошибка при загрузке договоров.")
    finally:
        db.close()
        await callback.answer()


async def confirm_cancel_contract(callback: types.CallbackQuery, state: FSMContext):
    from handlers.menu import main_menu_kb
    if callback.data == "cancel_contract_back":
        await callback.message.edit_text("Отмена операции.", reply_markup=main_menu_kb())
        await state.finish()
        await callback.answer()
        return

    contract_id_str = callback.data.replace("cancel_contract_", "")
    if not contract_id_str.isdigit():
        await callback.answer("Неверный формат.")
        return

    contract_id = int(contract_id_str)
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id, Contract.signed == True).first()
        if not contract:
            await callback.message.edit_text("Договор не найден или уже аннулирован.", reply_markup=main_menu_kb())
            await state.finish()
            return

        booking = db.query(Booking).filter(Booking.id == contract.booking_id).first()
        if booking:
            booking.contract_signed = False

        db.delete(contract)
        db.commit()
        await callback.message.edit_text("✅ Договор успешно аннулирован.", reply_markup=main_menu_kb())
        logger.info(f"Пользователь аннулировал договор ID={contract_id}")
    except Exception as e:
        logger.error(f"Ошибка при аннулировании: {e}")
        await callback.message.edit_text("Ошибка при аннулировании договора.")
    finally:
        db.close()
        await state.finish()
        await callback.answer()


# Регистрация хендлеров
def register_contracts_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(
        select_booking_callback,
        lambda c: c.data.startswith("select_booking_"),
        state=ContractStates.SELECT_BOOKING
    )
    dp.register_callback_query_handler(
        confirm_signature_callback,
        lambda c: c.data.startswith("sign_") or c.data == "cancel_contract",
        state=ContractStates.CONFIRM_SIGNATURE
    )
    dp.register_callback_query_handler(
        cancel_contract_callback,
        lambda c: c.data == "cancel_contract",
        state="*"
    )
    dp.register_callback_query_handler(
        confirm_cancel_contract,
        lambda c: c.data.startswith("cancel_contract_") or c.data == "cancel_contract_back",
        state=ContractStates.AWAITING_CANCEL_SELECTION
    )
