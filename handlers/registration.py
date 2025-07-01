from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from database import SessionLocal
from models.user import User, UserType
from loguru import logger

# --- STATES ---
class RegistrationFSM(StatesGroup):
    user_type = State()
    get_name = State()
    get_phone = State()
    get_company_name = State()
    get_inn = State()
    get_contact_person = State()

# Клавиатура выбора типа пользователя
user_type_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
user_type_keyboard.add("Владелец (физическое лицо)")
user_type_keyboard.add("Владелец (юридическое лицо)")
user_type_keyboard.add("Арендатор")

# Начало регистрации
async def start_registration(message: types.Message):
    await message.answer(
        "Добро пожаловать в сервис аренды автомобилей RentCar! Пожалуйста, выберите тип пользователя:",
        reply_markup=user_type_keyboard
    )
    await RegistrationFSM.user_type.set()

# Обработка выбора типа пользователя
async def user_type_handler(message: types.Message, state: FSMContext):
    text = message.text
    if text not in ["Владелец (физическое лицо)", "Владелец (юридическое лицо)", "Арендатор"]:
        await message.answer("Пожалуйста, выберите вариант из списка.")
        return

    await state.update_data(user_type=text)

    if text == "Владелец (физическое лицо)":
        await state.update_data(user_type_enum=UserType.OWNER_PHYSICAL)
        await message.answer("Введите ваше имя:")
        await RegistrationFSM.get_name.set()
    elif text == "Владелец (юридическое лицо)":
        await state.update_data(user_type_enum=UserType.OWNER_LEGAL)
        await message.answer("Введите название компании:")
        await RegistrationFSM.get_company_name.set()
    elif text == "Арендатор":
        await state.update_data(user_type_enum=UserType.RENTER)
        await message.answer("Введите ваше имя:")
        await RegistrationFSM.get_name.set()

# Обработка ввода имени
async def get_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите ваш номер телефона:")
    await RegistrationFSM.get_phone.set()

# Обработка ввода телефона
async def get_phone_handler(message: types.Message, state: FSMContext):
    global db
    data = await state.get_data()
    user_type_enum = data.get('user_type_enum')
    await state.update_data(phone=message.text)

    if user_type_enum == UserType.OWNER_LEGAL:
        await message.answer("Введите ИНН вашей компании:")
        await RegistrationFSM.get_inn.set()
    else:
        # Сохраняем физ. лицо или арендатора
        try:
            db = SessionLocal()
            telegram_id = message.from_user.id
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    user_type=user_type_enum,
                    name=data.get('name'),
                    phone=message.text,
                    registered=True
                )
                db.add(user)
            else:
                user.user_type = user_type_enum
                user.name = data.get('name')
                user.phone = message.text
                user.registered = True
            db.commit()
            await message.answer("Регистрация завершена. Спасибо!", reply_markup=ReplyKeyboardRemove())
            logger.info(f"User registered: {telegram_id}, type: {user.user_type}")
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            await message.answer("Произошла ошибка при регистрации. Попробуйте позже.")
        finally:
            db.close()
        await state.finish()

# Обработка ввода названия компании
async def get_company_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(company_name=message.text)
    await message.answer("Введите ваш номер телефона:")
    await RegistrationFSM.get_phone.set()

# Обработка ввода ИНН
async def get_inn_handler(message: types.Message, state: FSMContext):
    await state.update_data(company_inn=message.text)
    await message.answer("Введите контактное лицо компании:")
    await RegistrationFSM.get_contact_person.set()

# Обработка ввода контактного лица компании
async def get_contact_person_handler(message: types.Message, state: FSMContext):
    global db
    data = await state.get_data()
    await state.update_data(contact_person=message.text)

    # Сохраняем юридическое лицо
    try:
        db = SessionLocal()
        telegram_id = message.from_user.id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                user_type=data['user_type_enum'],
                company_name=data.get('company_name'),
                phone=data.get('phone'),
                company_inn=data.get('company_inn'),
                contact_person=data.get('contact_person'),
                registered=True
            )
            db.add(user)
        else:
            user.user_type = data['user_type_enum']
            user.company_name = data.get('company_name')
            user.phone = data.get('phone')
            user.company_inn = data.get('company_inn')
            user.contact_person = data.get('contact_person')
            user.registered = True
        db.commit()
        await message.answer("Регистрация завершена. Спасибо!", reply_markup=ReplyKeyboardRemove())
        logger.info(f"Legal entity registered: {telegram_id}")
    except Exception as e:
        logger.error(f"Error saving legal user: {e}")
        await message.answer("Произошла ошибка при регистрации. Попробуйте позже.")
    finally:
        db.close()

    await state.finish()

# Регистрация хендлеров

def register_registration_handlers(dp: Dispatcher):
    dp.register_message_handler(start_registration, commands=['start'], state="*")
    dp.register_message_handler(user_type_handler, state=RegistrationFSM.user_type)
    dp.register_message_handler(get_name_handler, state=RegistrationFSM.get_name)
    dp.register_message_handler(get_phone_handler, state=RegistrationFSM.get_phone)
    dp.register_message_handler(get_company_name_handler, state=RegistrationFSM.get_company_name)
    dp.register_message_handler(get_inn_handler, state=RegistrationFSM.get_inn)
    dp.register_message_handler(get_contact_person_handler, state=RegistrationFSM.get_contact_person)