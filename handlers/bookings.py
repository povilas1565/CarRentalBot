from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from sqlalchemy.orm import Session
from datetime import datetime
from loguru import logger

from database import SessionLocal
from models.booking import Booking, BookingStatus
from models.user import User
from models.car import Car
from handlers.calculator import calculate_rental_price
from keyboards.inline import (
    get_city_kb, get_car_kb,
    confirm_booking_kb, date_from_kb, date_to_kb
)


class BookingFSM(StatesGroup):
    select_city = State()
    select_car = State()
    select_date_from = State()
    select_date_to = State()
    confirm_booking = State()


# Шаг 1 — старт
async def start_booking(msg: types.Message, state: FSMContext):
    await msg.answer("Выберите город для аренды авто:", reply_markup=get_city_kb())
    await BookingFSM.select_city.set()


# Шаг 2 — выбор города
async def select_city_handler(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split(":")[1]
    await state.update_data(city=city)

    db: Session = SessionLocal()
    try:
        cars = db.query(Car).filter(Car.available == True, Car.city == city).all()
        if not cars:
            await callback.message.edit_text("🚫 Нет доступных авто в этом городе.")
            await state.finish()
            return

        cars_map = {f"{car.brand} {car.model} ({car.year})": car.id for car in cars}
        await state.update_data(available_cars=cars_map)

        await callback.message.edit_text(f"Город: {city}\nВыберите авто:", reply_markup=get_car_kb(cars_map))
        await BookingFSM.select_car.set()
    finally:
        db.close()


# Шаг 3 — выбор авто
async def select_car(callback: types.CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split(":")[1])
    data = await state.get_data()

    db: Session = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        # ⬇️ Проверяем регистрацию
        user_exists = db.query(User).filter(
            User.telegram_id == callback.from_user.id,
            User.registered == True
        ).first()
    finally:
        db.close()

    if not user_exists:
        # Сохраняем данные для восстановления
        await state.update_data(
            selected_car_id=car_id,
            booking_city=data.get("city"),
            available_cars=data.get("available_cars"),
            return_to="booking_car_selected"  # специальный маркер
        )
        from handlers.registration import start_registration
        await callback.message.answer("⚠️ Для бронирования необходимо зарегистрироваться.")
        await start_registration(callback.message, state)
        return

    # Если пользователь зарегистрирован - продолжаем бронирование
    await state.update_data(selected_car_id=car_id)

    if car and car.photo_file_id:
        await callback.message.answer_photo(photo=car.photo_file_id, caption=f"{car.brand} {car.model} ({car.year})")

    await callback.message.answer("Введите дату начала аренды (ДД.ММ.ГГГГ):", reply_markup=date_from_kb())
    await BookingFSM.select_date_from.set()

# Шаг 4 — дата начала
async def select_date_from(msg: types.Message, state: FSMContext):
    try:
        date_from = datetime.strptime(msg.text.strip(), "%d.%m.%Y").date()
        if date_from < datetime.today().date():
            raise ValueError()
        await state.update_data(date_from=date_from)

        await msg.answer("Введите дату окончания бронирования в формате ДД.MM.ГГГГ:", reply_markup=date_to_kb())
        await BookingFSM.select_date_to.set()
    except Exception:
        await msg.answer("❌ Некорректная дата. Введите в формате ДД.ММ.ГГГГ, не в прошлом.",
                         reply_markup=date_from_kb())


# Шаг 5 — дата окончания
async def select_date_to(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        date_to = datetime.strptime(msg.text.strip(), "%d.%m.%Y").date()
        date_from = data["date_from"]
        if date_to < date_from:
            raise ValueError()
        await state.update_data(date_to=date_to)

        db: Session = SessionLocal()
        car = db.query(Car).filter(Car.id == data["selected_car_id"]).first()
        db.close()

        total_price = calculate_rental_price(
            date_from=datetime.combine(date_from, datetime.min.time()),
            date_to=datetime.combine(date_to, datetime.min.time()),
            price_per_day=car.price_per_day,
            discount=car.discount or 0.0
        )
        await state.update_data(total_price=total_price)

        car_name = next((name for name, id_ in data["available_cars"].items() if id_ == car.id), "автомобиль")

        summary = (
            f"Подтвердите бронирование:\n"
            f"🚗 {car_name}\n"
            f"📅 С {date_from.strftime('%d.%m.%Y')} по {date_to.strftime('%d.%m.%Y')}\n"
            f"💶 Итого: {total_price:.2f} €\n"
            "Подтверждаете?"
        )
        await msg.answer(summary, reply_markup=confirm_booking_kb())
        await BookingFSM.confirm_booking.set()
    except Exception:
        await msg.answer("❌ Некорректная дата. Попробуйте снова.", reply_markup=date_to_kb())


# Шаг 6 — подтверждение
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "confirm:no":
        await callback.message.edit_text("❌ Бронирование отменено.")
        await state.finish()
        return

    data = await state.get_data()
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
        car = db.query(Car).filter(Car.id == data["selected_car_id"]).first()

        if not (user and car and car.available):
            await callback.message.edit_text("🚫 Пользователь или авто не найдено.")
            await state.finish()
            return

        booking = Booking(
            renter_id=user.id,
            car_id=car.id,
            date_from=data["date_from"],
            date_to=data["date_to"],
            total_price=data["total_price"],
            status=BookingStatus.CONFIRMED
        )
        db.add(booking)
        car.available = False
        db.commit()

        await callback.message.edit_text("✅ Бронирование подтверждено!")
        logger.info(f"Booking: user={user.id}, car={car.id}")
    except Exception as e:
        logger.error(f"Ошибка бронирования: {e}")
        await callback.message.edit_text("Ошибка при бронировании.")
    finally:
        db.close()

    await state.finish()


# Отмена
async def cancel(msg: types.Message, state: FSMContext):
    from handlers.menu import main_menu_kb
    await msg.answer("⛔ Операция отменена.", reply_markup=main_menu_kb())
    await state.finish()


# 🔙 Назад — город
async def back_to_city(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выберите город:", reply_markup=get_city_kb())
    await BookingFSM.select_city.set()


# 🔙 Назад — авто
async def back_to_car(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cars_map = data.get("available_cars", {})
    await callback.message.edit_text("Выберите автомобиль:", reply_markup=get_car_kb(cars_map))
    await BookingFSM.select_car.set()


# 🔙 Назад — к выбору авто из ввода даты
async def back_to_car_from_date(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cars_map = data.get("available_cars", {})
    await callback.message.edit_text("Выберите автомобиль:", reply_markup=get_car_kb(cars_map))
    await BookingFSM.select_car.set()


# 🔙 Назад — к дате начала из даты окончания
async def back_to_date_from(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите дату начала бронирования в формате ДД.ММ.ГГГГ:",
                                     reply_markup=date_from_kb())
    await BookingFSM.select_date_from.set()


# Регистрация хендлеров
def register_bookings_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(select_city_handler, lambda c: c.data.startswith("city:"),
                                       state=BookingFSM.select_city)
    dp.register_callback_query_handler(select_car, lambda c: c.data.startswith("car:"), state=BookingFSM.select_car)
    dp.register_message_handler(select_date_from, state=BookingFSM.select_date_from)
    dp.register_message_handler(select_date_to, state=BookingFSM.select_date_to)
    dp.register_callback_query_handler(confirm_booking, lambda c: c.data.startswith("confirm:"),
                                       state=BookingFSM.confirm_booking)
    dp.register_callback_query_handler(back_to_city, lambda c: c.data == "back:city", state="*")
    dp.register_callback_query_handler(back_to_car, lambda c: c.data == "back:dates", state="*")
    dp.register_callback_query_handler(back_to_car_from_date, lambda c: c.data == "back:car", state="*")
    dp.register_callback_query_handler(back_to_date_from, lambda c: c.data == "back:date_from", state="*")
