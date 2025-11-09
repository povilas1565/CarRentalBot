from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from database import SessionLocal
from keyboards.inline import user_type_keyboard, cancel_keyboard
from models.user import User, UserType
from models.car import Car
from loguru import logger
import re


def normalize_phone(raw: str) -> str:
    s = (raw or "").strip()
    # убрать пробелы/скобки/тире/точки
    s = re.sub(r"[()\s\-\.]", "", s)
    # 00... -> +...
    if s.startswith("00"):
        s = "+" + s[2:]
    return s


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
    phone = normalize_phone(message.text)
    await state.update_data(phone=phone)

    data = await state.get_data()
    user_type = data.get("user_type_enum")

    if user_type == UserType.OWNER_LEGAL:
        await message.answer("Введите PIB компании:", reply_markup=cancel_keyboard())
        await RegistrationFSM.get_inn.set()
    else:
        await save_user_and_finish(message, state, await state.get_data())


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
    from keyboards.inline import date_from_kb
    db = SessionLocal()
    try:
        telegram_id = message.from_user.id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            user = User(
                telegram_id=telegram_id,
                user_type=data.get("user_type_enum"),
                name=data.get("name"),
                phone=data.get("phone"),
                company_name=data.get("company_name"),
                company_inn=data.get("company_inn"),
                contact_person=data.get("contact_person"),
                registered=True,
            )
            db.add(user)
        else:
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

        # ⬇️ ВАЖНО: Проверяем, нужно ли продолжить бронирование ИЛИ добавление авто
        state_data = await state.get_data()

        if state_data.get("resume_booking"):
            # Восстанавливаем данные бронирования
            from handlers.bookings import BookingFSM

            # Завершаем состояние регистрации
            await state.finish()

            # Восстанавливаем выбранный автомобиль
            car_id = state_data.get("selected_car_id")
            db_car = SessionLocal()
            car = db_car.query(Car).filter(Car.id == car_id).first()
            db_car.close()

            if car and car.photo_file_id:
                await message.answer_photo(
                    photo=car.photo_file_id,
                    caption=f"{car.brand} {car.model} ({car.year})"
                )

            # Продолжаем с выбора даты
            await message.answer(
                "Отлично! Теперь укажите дату начала аренды (ДД.ММ.ГГГГ):",
                reply_markup=date_from_kb()
            )
            await BookingFSM.select_date_from.set()
            return

        elif state_data.get("resume_add_car"):
            # Восстанавливаем добавление авто
            from handlers.cars import AddCarFSM

            # Завершаем состояние регистрации
            await state.finish()

            # Продолжаем с добавления авто
            await message.answer("Отлично! Теперь вы можете добавить автомобиль.", reply_markup=main_menu_kb())
            # Можно автоматически запустить процесс добавления авто:
            # await message.answer("Введите марку:", reply_markup=kb_back())
            # await AddCarFSM.brand.set()

    except Exception as e:
        import traceback
        logger.error(f"Registration error: {e}\n{traceback.format_exc()}")
        await message.answer("❌ Ошибка при регистрации. Попробуйте позже.", reply_markup=main_menu_kb())
    finally:
        db.close()
        # Завершаем состояние только если не перешли к другому процессу
        current_state = await state.get_state()
        if current_state and "RegistrationFSM" in current_state:
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
    dp.register_callback_query_handler(user_type_callback_handler, lambda c: c.data.startswith("user_type_"),
                                       state=RegistrationFSM.user_type)
    dp.register_callback_query_handler(cancel_registration_handler, lambda c: c.data == "cancel_registration",
                                       state="*")
    dp.register_message_handler(get_name_handler, state=RegistrationFSM.get_name)
    dp.register_message_handler(get_company_name_handler, state=RegistrationFSM.get_company_name)
    dp.register_message_handler(get_phone_handler, state=RegistrationFSM.get_phone)
    dp.register_message_handler(get_inn_handler, state=RegistrationFSM.get_inn)
    dp.register_message_handler(get_contact_person_handler, state=RegistrationFSM.get_contact_person)
