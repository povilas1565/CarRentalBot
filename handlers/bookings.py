from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from database import SessionLocal
from models.booking import Booking, BookingStatus
from models.user import User
from models.car import Car
from handlers.calculator import calculate_rental_price
from datetime import datetime
from loguru import logger


# --- STATES ---
class BookingFSM(StatesGroup):
    select_city = State()
    select_car = State()
    select_date_from = State()
    select_date_to = State()
    confirm_booking = State()


# --- START BOOKING: выбор города ---
async def start_booking(msg: types.Message, state: FSMContext):
    cities = ["Москва", "Санкт-Петербург", "Казань"]  # <-- список городов можно подтягивать из базы или константа
    keyboard = InlineKeyboardMarkup(row_width=2)
    for city in cities:
        keyboard.insert(InlineKeyboardButton(text=city, callback_data=f"city:{city}"))

    await msg.answer("Выберите город для аренды автомобиля:", reply_markup=keyboard)
    await BookingFSM.select_city.set()


# --- HANDLER ВЫБОРА ГОРОДА ---
async def select_city_handler(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":")[1]
    await state.update_data(city=city)
    db = SessionLocal()
    try:
        cars = db.query(Car).filter(Car.available == True, Car.city == city).all()
        if not cars:
            await callback.message.answer("В выбранном городе нет доступных автомобилей.")
            await state.finish()
            await callback.answer()
            return

        # Формируем клавиатуру с машинами (текст + id)
        keyboard = []
        cars_map = {}
        for car in cars:
            car_name = f"{car.brand} {car.model} ({car.year})"
            keyboard.append([KeyboardButton(car_name)])
            cars_map[car_name] = car.id

        keyboard.append([KeyboardButton("Отмена")])
        markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

        await state.update_data(available_cars=cars_map)

        await callback.message.answer("Выберите автомобиль для бронирования:", reply_markup=markup)
        await BookingFSM.select_car.set()
        await callback.answer()
    finally:
        db.close()


# --- SELECT CAR: выбор машины из клавиатуры, показ фото ---
async def select_car(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Бронирование отменено.", reply_markup=ReplyKeyboardRemove())
        await state.finish()
        return

    data = await state.get_data()
    cars_map = data.get("available_cars", {})

    if msg.text not in cars_map:
        await msg.answer("Пожалуйста, выберите автомобиль из списка.")
        return

    car_id = cars_map[msg.text]
    await state.update_data(selected_car_id=car_id)

    db = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            await msg.answer("Автомобиль не найден.")
            await state.finish()
            return

        # Если есть фото, отправляем
        if car.photo_file_id:
            await msg.answer_photo(photo=car.photo_file_id, caption=msg.text)

    finally:
        db.close()

    await msg.answer("Введите дату начала бронирования в формате ДД.MM.ГГГГ:", reply_markup=ReplyKeyboardRemove())
    await BookingFSM.select_date_from.set()


# --- SELECT DATE FROM ---
async def select_date_from(msg: types.Message, state: FSMContext):
    date_text = msg.text.strip()
    try:
        date_from = datetime.strptime(date_text, "%d.%m.%Y").date()
        if date_from < datetime.today().date():
            raise ValueError("Дата начала не может быть в прошлом.")
    except Exception:
        await msg.answer("Введите корректную дату начала в формате ДД.MM.ГГГГ, не в прошлом.")
        return

    await state.update_data(date_from=date_from)
    await msg.answer("Введите дату окончания бронирования в формате ДД.MM.ГГГГ:")
    await BookingFSM.select_date_to.set()


# --- SELECT DATE TO ---
async def select_date_to(msg: types.Message, state: FSMContext):
    date_text = msg.text.strip()
    data = await state.get_data()
    try:
        date_to = datetime.strptime(date_text, "%d.%m.%Y").date()
        date_from = data.get("date_from")
        if date_to < date_from:
            await msg.answer("Дата окончания не может быть раньше даты начала.")
            return
    except Exception:
        await msg.answer("Введите корректную дату окончания в формате ДД.MM.ГГГГ.")
        return

    await state.update_data(date_to=date_to)

    car_id = data.get("selected_car_id")
    db = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            await msg.answer("Автомобиль не найден.")
            await state.finish()
            return

        discount = car.discount if car.discount else 0.0

        total_price = calculate_rental_price(
            date_from=datetime.combine(date_from, datetime.min.time()),
            date_to=datetime.combine(date_to, datetime.min.time()),
            price_per_day=car.price_per_day,
            discount=discount
        )

        await state.update_data(total_price=total_price)

        # Получаем название машины для вывода
        cars_map = data.get("available_cars")
        car_name = next((name for name, id_ in cars_map.items() if id_ == car_id), "автомобиль")

        summary = (
            f"Подтвердите бронирование:\n"
            f"Автомобиль: {car_name}\n"
            f"С {date_from.strftime('%d.%m.%Y')} по {date_to.strftime('%d.%m.%Y')}\n"
            f"Итого: {total_price:.2f} €\n\n"
            "Подтверждаете? (да/нет)"
        )
        await msg.answer(summary)
        await BookingFSM.confirm_booking.set()
    finally:
        db.close()


# --- CONFIRM BOOKING ---
async def confirm_booking(msg: types.Message, state: FSMContext):
    text = msg.text.lower()
    if text not in ["да", "нет"]:
        await msg.answer("Пожалуйста, ответьте 'да' или 'нет'.")
        return

    if text == "нет":
        await msg.answer("Бронирование отменено.", reply_markup=ReplyKeyboardRemove())
        await state.finish()
        return

    data = await state.get_data()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == msg.from_user.id).first()
        if not user:
            await msg.answer("Вы не зарегистрированы. Пожалуйста, используйте /start для регистрации.")
            await state.finish()
            return

        car = db.query(Car).filter(Car.id == data.get("selected_car_id")).first()
        if not car or not car.available:
            await msg.answer("Выбранный автомобиль недоступен.")
            await state.finish()
            return

        booking = Booking(
            renter_id=user.id,
            car_id=car.id,
            date_from=data.get("date_from"),
            date_to=data.get("date_to"),
            total_price=data.get("total_price"),
            status=BookingStatus.CONFIRMED,
        )
        db.add(booking)
        car.available = False
        db.commit()

        await msg.answer("Бронирование успешно создано!", reply_markup=ReplyKeyboardRemove())
        logger.info(f"Booking created: user {user.id} car {car.id}")
    except Exception as e:
        logger.error(f"Ошибка при создании бронирования: {e}")
        await msg.answer("Ошибка при бронировании. Попробуйте позже.")
    finally:
        db.close()

    await state.finish()


# --- CANCEL ---
async def cancel(msg: types.Message, state: FSMContext):
    await msg.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    await state.finish()


# --- REGISTER HANDLERS ---
def register_bookings_handlers(dp: Dispatcher):
    dp.register_message_handler(start_booking, commands=["book"], state="*")
    dp.register_message_handler(cancel, commands=["cancel"], state="*")
    dp.register_callback_query_handler(select_city_handler, lambda c: c.data.startswith("city:"), state=BookingFSM.select_city)
    dp.register_message_handler(select_car, state=BookingFSM.select_car)
    dp.register_message_handler(select_date_from, state=BookingFSM.select_date_from)
    dp.register_message_handler(select_date_to, state=BookingFSM.select_date_to)
    dp.register_message_handler(confirm_booking, lambda msg: msg.text.lower() in ["да", "нет"], state=BookingFSM.confirm_booking)