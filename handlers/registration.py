from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from database import SessionLocal
from keyboards.inline import user_type_keyboard, cancel_keyboard
from models.user import User, UserType
from loguru import logger


class RegistrationFSM(StatesGroup):
    user_type = State()
    get_name = State()
    get_phone = State()
    get_company_name = State()
    get_inn = State()
    get_contact_person = State()


async def start_registration(message: types.Message, state: FSMContext):
    await message.answer("Выберите тип пользователя:", reply_markup=user_type_keyboard())
    await RegistrationFSM.user_type.set()


async def user_type_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    if data == "user_type_owner_physical":
        await state.update_data(user_type_enum=UserType.OWNER_PHYSICAL)
        await callback.message.edit_text("Введите ваше имя:", reply_markup=cancel_keyboard())
        await RegistrationFSM.get_name.set()

    elif data == "user_type_owner_legal":
        await state.update_data(user_type_enum=UserType.OWNER_LEGAL)
        await callback.message.edit_text("Введите название компании:", reply_markup=cancel_keyboard())
        await RegistrationFSM.get_company_name.set()

    elif data == "user_type_renter":
        await state.update_data(user_type_enum=UserType.RENTER)
        await callback.message.edit_text("Введите ваше имя:", reply_markup=cancel_keyboard())
        await RegistrationFSM.get_name.set()

    await callback.answer()


async def get_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш номер телефона:", reply_markup=cancel_keyboard())
    await RegistrationFSM.get_phone.set()


async def get_company_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(company_name=message.text)
    await message.answer("Введите номер телефона:", reply_markup=cancel_keyboard())
    await RegistrationFSM.get_phone.set()


async def get_phone_handler(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    user_type = data.get("user_type_enum")

    if user_type == UserType.OWNER_LEGAL:
        await message.answer("Введите ИНН компании:", reply_markup=cancel_keyboard())
        await RegistrationFSM.get_inn.set()
    else:
        await save_user_and_finish(message, state, data)


async def get_inn_handler(message: types.Message, state: FSMContext):
    await state.update_data(company_inn=message.text)
    await message.answer("Введите контактное лицо:", reply_markup=cancel_keyboard())
    await RegistrationFSM.get_contact_person.set()


async def get_contact_person_handler(message: types.Message, state: FSMContext):
    await state.update_data(contact_person=message.text)
    data = await state.get_data()
    await save_user_and_finish(message, state, data)


async def save_user_and_finish(message: types.Message, state: FSMContext, data: dict):
    from handlers.menu import main_menu_kb
    db = SessionLocal()
    try:
        telegram_id = message.from_user.id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            user = User(telegram_id=telegram_id)
            db.add(user)

        user.user_type = data.get("user_type_enum")
        user.name = data.get("name")
        user.phone = data.get("phone")
        user.company_name = data.get("company_name")
        user.company_inn = data.get("company_inn")
        user.contact_person = data.get("contact_person")
        user.registered = True

        db.commit()
        await message.answer("✅ Регистрация завершена. Спасибо!", reply_markup=main_menu_kb())
        logger.info(f"User registered: {telegram_id}, type: {user.user_type}")
    except Exception as e:
        logger.error(f"Registration error: {e}")
        await message.answer("❌ Ошибка при регистрации. Попробуйте позже.", reply_markup=main_menu_kb())
    finally:
        db.close()
        # ⬇️ если регистрация запущена прямо из бронирования — продолжаем бронирование
        data_after = await state.get_data()
        if data_after.get("resume_booking"):
            from handlers.bookings import BookingFSM, date_from_kb
            await message.answer("Отлично! Теперь укажите дату начала аренды (ДД.ММ.ГГГГ):", reply_markup=date_from_kb())
            await BookingFSM.select_date_from.set()
            return
        await state.finish()


async def cancel_registration_handler(event: types.Message | types.CallbackQuery, state: FSMContext):
    from handlers.menu import main_menu_kb
    await state.finish()

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text("🚫 Регистрация отменена.", reply_markup=main_menu_kb())
        await event.answer()
    else:
        await event.answer("🚫 Регистрация отменена.", reply_markup=main_menu_kb())


def register_registration_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(user_type_callback_handler, lambda c: c.data.startswith("user_type_"), state=RegistrationFSM.user_type)
    dp.register_callback_query_handler(cancel_registration_handler, lambda c: c.data == "cancel_registration", state="*")
    dp.register_message_handler(get_name_handler, state=RegistrationFSM.get_name)
    dp.register_message_handler(get_company_name_handler, state=RegistrationFSM.get_company_name)
    dp.register_message_handler(get_phone_handler, state=RegistrationFSM.get_phone)
    dp.register_message_handler(get_inn_handler, state=RegistrationFSM.get_inn)
    dp.register_message_handler(get_contact_person_handler, state=RegistrationFSM.get_contact_person)
