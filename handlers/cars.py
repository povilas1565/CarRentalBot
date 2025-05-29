from aiogram import types, Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from sqlalchemy.orm import Session
from database import SessionLocal
from models.car import Car
from models.user import User
from loguru import logger


# --- STATES ---
class AddCarFSM(StatesGroup):
    brand = State()
    model = State()
    year = State()
    license_plate = State()
    vin = State()
    price = State()
    discount = State()          # новое состояние для скидки
    rental_terms = State()
    confirm = State()


class EditCarFSM(StatesGroup):
    choose_car = State()
    choose_field = State()
    enter_value = State()
    confirm_delete = State()


# --- ADD CAR HANDLERS ---

async def add_car_start(msg: types.Message, state: FSMContext):
    await msg.answer("Введите марку автомобиля:")
    await AddCarFSM.brand.set()


async def get_brand(msg: types.Message, state: FSMContext):
    await state.update_data(brand=msg.text)
    await msg.answer("Введите модель автомобиля:")
    await AddCarFSM.model.set()


async def get_model(msg: types.Message, state: FSMContext):
    await state.update_data(model=msg.text)
    await msg.answer("Введите год выпуска:")
    await AddCarFSM.year.set()


async def get_year(msg: types.Message, state: FSMContext):
    try:
        year = int(msg.text)
        if not (1900 <= year <= 2100):
            raise ValueError
        await state.update_data(year=year)
        await msg.answer("Введите номерной знак (можно пропустить):")
        await AddCarFSM.license_plate.set()
    except ValueError:
        await msg.answer("Введите корректный год (1900–2100):")


async def get_license(msg: types.Message, state: FSMContext):
    await state.update_data(license_plate=msg.text)
    await msg.answer("Введите VIN (можно пропустить):")
    await AddCarFSM.vin.set()


async def get_vin(msg: types.Message, state: FSMContext):
    await state.update_data(vin=msg.text)
    await msg.answer("Введите цену аренды за день (в €):")
    await AddCarFSM.price.set()


async def get_price(msg: types.Message, state: FSMContext):
    try:
        price = float(msg.text.replace(",", "."))
        if price <= 0:
            raise ValueError
        await state.update_data(price_per_day=price)
        await msg.answer("Введите скидку в процентах (0 если нет):")
        await AddCarFSM.discount.set()
    except ValueError:
        await msg.answer("Введите положительное число.")


async def get_discount(msg: types.Message, state: FSMContext):
    try:
        discount = float(msg.text.replace(",", "."))
        if not (0 <= discount <= 100):
            raise ValueError
        await state.update_data(discount=discount)
        await msg.answer("Введите условия аренды (или 'нет'):")
        await AddCarFSM.rental_terms.set()
    except ValueError:
        await msg.answer("Введите корректное число от 0 до 100.")


async def get_terms(msg: types.Message, state: FSMContext):
    terms = "" if msg.text.lower() == "нет" else msg.text
    await state.update_data(rental_terms=terms)

    data = await state.get_data()
    summary = (
        f"Проверьте данные:\n"
        f"Марка: {data['brand']}\n"
        f"Модель: {data['model']}\n"
        f"Год: {data['year']}\n"
        f"Номерной знак: {data['license_plate']}\n"
        f"VIN: {data['vin']}\n"
        f"Цена: {data['price_per_day']} €\n"
        f"Скидка: {data.get('discount', 0)} %\n"
        f"Условия: {terms or 'нет'}\n\n"
        f"Подтвердите добавление? (да/нет)"
    )
    await msg.answer(summary)
    await AddCarFSM.confirm.set()


async def confirm_car(msg: types.Message, state: FSMContext):
    text = msg.text.lower()
    if text == "да":
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == msg.from_user.id).first()
            if not user:
                await msg.answer("Сначала зарегистрируйтесь (/start).")
                return await state.finish()

            data = await state.get_data()
            car = Car(
                owner_id=user.id,
                brand=data["brand"],
                model=data["model"],
                year=data["year"],
                license_plate=data["license_plate"],
                vin=data["vin"],
                price_per_day=data["price_per_day"],
                discount=data.get("discount", 0.0),
                rental_terms=data["rental_terms"],
                available=True
            )
            db.add(car)
            db.commit()
            await msg.answer("Автомобиль успешно добавлен!")
        except Exception as e:
            logger.error(f"Ошибка добавления машины: {e}")
            await msg.answer("Произошла ошибка. Попробуйте позже.")
        finally:
            db.close()
        await state.finish()
    elif text == "нет":
        await msg.answer("Добавление отменено.")
        await state.finish()
    else:
        await msg.answer("Пожалуйста, введите 'да' или 'нет'.")


# --- MY CARS HANDLERS ---

async def list_user_cars(msg: types.Message, state: FSMContext):
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == msg.from_user.id).first()
        if not user:
            await msg.answer("Сначала зарегистрируйтесь (/start).")
            return

        cars = db.query(Car).filter(Car.owner_id == user.id).all()
        if not cars:
            await msg.answer("У вас нет добавленных автомобилей.")
            return

        buttons = [[KeyboardButton(text=f"{car.brand} {car.model} ({car.year})")]
                   for car in cars]
        buttons.append([KeyboardButton(text="Отмена")])
        markup = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

        car_map = {f"{car.brand} {car.model} ({car.year})": car.id for car in cars}
        await state.update_data(car_map=car_map)

        await msg.answer("Выберите автомобиль:", reply_markup=markup)
        await EditCarFSM.choose_car.set()
    except Exception as e:
        logger.error(f"Ошибка получения списка машин: {e}")
        await msg.answer("Ошибка. Попробуйте позже.")
    finally:
        db.close()


async def choose_edit_field(msg: types.Message, state: FSMContext):
    if msg.text == "Отмена":
        await msg.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return await state.finish()

    data = await state.get_data()
    car_id = data.get("car_map", {}).get(msg.text)
    if not car_id:
        await msg.answer("Пожалуйста, выберите автомобиль из списка.")
        return

    await state.update_data(edit_car_id=car_id)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Марка"), KeyboardButton(text="Модель")],
            [KeyboardButton(text="Год"), KeyboardButton(text="Цена")],
            [KeyboardButton(text="Скидка"), KeyboardButton(text="Условия")],
            [KeyboardButton(text="Удалить")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )
    await msg.answer("Что вы хотите изменить?", reply_markup=keyboard)
    await EditCarFSM.choose_field.set()


async def get_new_value(msg: types.Message, state: FSMContext):
    if msg.text == "Удалить":
        await msg.answer("Вы уверены, что хотите удалить автомобиль? (да/нет)", reply_markup=ReplyKeyboardRemove())
        return await EditCarFSM.confirm_delete.set()
    elif msg.text == "Отмена":
        await msg.answer("Операция отменена.", reply_markup=ReplyKeyboardRemove())
        return await state.finish()
    elif msg.text in ["Марка", "Модель", "Год", "Цена", "Скидка", "Условия"]:
        await state.update_data(edit_field=msg.text)
        await msg.answer(f"Введите новое значение для {msg.text}:", reply_markup=ReplyKeyboardRemove())
        await EditCarFSM.enter_value.set()
    else:
        await msg.answer("Выберите вариант из меню.")


async def update_car_value(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    car_id = data.get("edit_car_id")
    field = data.get("edit_field")

    db: Session = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            await msg.answer("Автомобиль не найден.")
            return await state.finish()

        if field == "Марка":
            car.brand = msg.text
        elif field == "Модель":
            car.model = msg.text
        elif field == "Год":
            try:
                car.year = int(msg.text)
            except ValueError:
                await msg.answer("Введите корректный год.")
                return
        elif field == "Цена":
            try:
                price = float(msg.text.replace(",", "."))
                if price <= 0:
                    raise ValueError
                car.price_per_day = price
            except ValueError:
                await msg.answer("Введите положительное число.")
                return
        elif field == "Скидка":
            try:
                discount = float(msg.text.replace(",", "."))
                if not (0 <= discount <= 100):
                    await msg.answer("Введите число от 0 до 100.")
                    return
                car.discount = discount
            except ValueError:
                await msg.answer("Введите корректное число от 0 до 100.")
                return
        elif field == "Условия":
            car.rental_terms = msg.text

        db.commit()
        await msg.answer(f"Поле '{field}' обновлено успешно.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении: {e}")
        await msg.answer("Ошибка при обновлении. Проверьте данные.")
    finally:
        db.close()
    await state.finish()


async def delete_car(msg: types.Message, state: FSMContext):
    if msg.text.lower() == "да":
        data = await state.get_data()
        car_id = data.get("edit_car_id")

        db: Session = SessionLocal()
        try:
            car = db.query(Car).filter(Car.id == car_id).first()
            if car:
                db.delete(car)
                db.commit()
                await msg.answer("Автомобиль удален.")
            else:
                await msg.answer("Автомобиль не найден.")
        except Exception as e:
            logger.error(f"Ошибка при удалении: {e}")
            await msg.answer("Ошибка при удалении.")
        finally:
            db.close()
    else:
        await msg.answer("Удаление отменено.")
    await state.finish()


# --- REGISTER HANDLERS ---
def register_cars_handlers(dp: Dispatcher):
    dp.register_message_handler(add_car_start, commands=["add_car"], state="*")
    dp.register_message_handler(get_brand, state=AddCarFSM.brand)
    dp.register_message_handler(get_model, state=AddCarFSM.model)
    dp.register_message_handler(get_year, state=AddCarFSM.year)
    dp.register_message_handler(get_license, state=AddCarFSM.license_plate)
    dp.register_message_handler(get_vin, state=AddCarFSM.vin)
    dp.register_message_handler(get_price, state=AddCarFSM.price)
    dp.register_message_handler(get_discount, state=AddCarFSM.discount)  # новый обработчик скидки
    dp.register_message_handler(get_terms, state=AddCarFSM.rental_terms)
    dp.register_message_handler(confirm_car, state=AddCarFSM.confirm)

    dp.register_message_handler(list_user_cars, commands=["my_cars"], state="*")
    dp.register_message_handler(choose_edit_field, state=EditCarFSM.choose_car)
    dp.register_message_handler(get_new_value, state=EditCarFSM.choose_field)
    dp.register_message_handler(update_car_value, state=EditCarFSM.enter_value)
    dp.register_message_handler(delete_car, state=EditCarFSM.confirm_delete)