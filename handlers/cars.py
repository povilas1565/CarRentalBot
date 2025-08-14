from aiogram import types, Dispatcher
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from database import SessionLocal
from keyboards.inline import kb_back, kb_skip_cancel, kb_confirm
from models.car import Car
from models.user import User
from loguru import logger


class AddCarFSM(StatesGroup):
    brand = State()
    model = State()
    year = State()
    license_plate = State()
    vin = State()
    price = State()
    discount = State()
    rental_terms = State()
    city = State()
    photo = State()
    confirm = State()


class EditCarFSM(StatesGroup):
    choose_car = State()
    choose_field = State()
    enter_value = State()
    confirm_delete = State()
    upload_photo = State()


# ===== Общая отмена =====
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    from handlers.menu import main_menu_kb
    await callback.message.edit_text("❌ Отменено.", reply_markup=main_menu_kb())
    await state.finish()
    await callback.answer()


# ===== Добавление авто =====
async def add_car_start(msg: types.Message, state: FSMContext):
    await msg.answer("Введите марку:", reply_markup=kb_back())
    await AddCarFSM.brand.set()


async def get_brand(msg, state: FSMContext):
    await state.update_data(brand=msg.text)
    await msg.answer("Введите модель:", reply_markup=kb_back())
    await AddCarFSM.model.set()


async def get_model(msg, state: FSMContext):
    await state.update_data(model=msg.text)
    await msg.answer("Введите год:", reply_markup=kb_back())
    await AddCarFSM.year.set()


async def get_year(msg, state: FSMContext):
    try:
        year = int(msg.text)
        if not (1900 <= year <= 2100):
            raise
        await state.update_data(year=year)
        await msg.answer("Номерной знак:", reply_markup=kb_skip_cancel())
        await AddCarFSM.license_plate.set()
    except:
        await msg.answer("Год 1900–2100:", reply_markup=kb_back())


# ===== Пропуски =====
async def skip_license(callback: CallbackQuery, state: FSMContext):
    await state.update_data(license_plate=None)
    await callback.message.edit_text("VIN:", reply_markup=kb_skip_cancel())
    await AddCarFSM.vin.set()
    await callback.answer()


async def skip_vin(callback: CallbackQuery, state: FSMContext):
    await state.update_data(vin=None)
    await callback.message.edit_text("Цена (€):", reply_markup=kb_back())
    await AddCarFSM.price.set()
    await callback.answer()


async def skip_terms(callback: CallbackQuery, state: FSMContext):
    await state.update_data(rental_terms=None)
    await callback.message.edit_text("Город:", reply_markup=kb_back())
    await AddCarFSM.city.set()
    await callback.answer()


async def skip_photo(callback: CallbackQuery, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await confirm_summary(callback.message, state)
    await callback.answer()


# ===== Основные шаги =====
async def get_license(msg, state: FSMContext):
    await state.update_data(license_plate=msg.text)
    await msg.answer("VIN:", reply_markup=kb_skip_cancel())
    await AddCarFSM.vin.set()


async def get_vin(msg, state: FSMContext):
    await state.update_data(vin=msg.text)
    await msg.answer("Цена (€):", reply_markup=kb_back())
    await AddCarFSM.price.set()


async def get_price(msg, state: FSMContext):
    try:
        price = float(msg.text.replace(",", "."))
        if price <= 0:
            raise
        await state.update_data(price_per_day=price)
        await msg.answer("Скидка 0–100%:", reply_markup=kb_back())
        await AddCarFSM.discount.set()
    except:
        await msg.answer("Укажите €:", reply_markup=kb_back())


async def get_discount(msg, state: FSMContext):
    try:
        disc = float(msg.text.replace(",", "."))
        if not (0 <= disc <= 100):
            raise
        await state.update_data(discount=disc)
        await msg.answer("Условия аренды:", reply_markup=kb_skip_cancel())
        await AddCarFSM.rental_terms.set()
    except:
        await msg.answer("Скидка 0–100:", reply_markup=kb_back())


async def get_terms(msg, state: FSMContext):
    await state.update_data(rental_terms=msg.text)
    await msg.answer("Город:", reply_markup=kb_back())
    await AddCarFSM.city.set()


async def get_city(msg, state: FSMContext):
    await state.update_data(city=msg.text)
    await msg.answer("Фото или 'Пропустить':", reply_markup=kb_skip_cancel())
    await AddCarFSM.photo.set()


async def get_photo(msg, state: FSMContext):
    if msg.photo:
        await state.update_data(photo_file_id=msg.photo[-1].file_id)
    elif msg.text.lower() == "пропустить":
        await state.update_data(photo_file_id=None)
    else:
        await msg.answer("Фото или Пропустить:", reply_markup=kb_skip_cancel())
        return

    await confirm_summary(msg, state)


# ===== Подтверждение =====
async def confirm_summary(message_or_callback, state: FSMContext):
    d = await state.get_data()
    summary = (
        f"{d['brand']} {d['model']} ({d['year']})\n"
        f"Знак: {d['license_plate']}\nVIN: {d['vin']}\n"
        f"Цена: {d['price_per_day']} €\nСкидка: {d['discount']}%\n"
        f"{d['rental_terms']}\nГород: {d['city']}\nФото: {'есть' if d.get('photo_file_id') else 'нет'}"
    )

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(f"Проверьте:\n{summary}\nДобавить?", reply_markup=kb_confirm())
    else:
        await message_or_callback.edit_text(f"Проверьте:\n{summary}\nДобавить?", reply_markup=kb_confirm())
    await AddCarFSM.confirm.set()


async def confirm_add(callback: CallbackQuery, state: FSMContext):
    if callback.data == "confirm_yes":
        d = await state.get_data()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == callback.from_user.id).first()
            if not user:
                await callback.message.edit_text("❌ Сначала зарегистрируйтесь.")
                return
            car = Car(
                owner_id=user.id,
                brand=d["brand"],
                model=d["model"],
                year=d["year"],
                license_plate=d["license_plate"],
                vin=d["vin"],
                price_per_day=d["price_per_day"],
                discount=d["discount"],
                rental_terms=d["rental_terms"],
                city=d["city"],
                photo_file_id=d.get("photo_file_id"),
                available=True
            )
            db.add(car)
            db.commit()
            await callback.message.edit_text("🚗 Авто добавлено.")
        except Exception as e:
            logger.error(f"Add car error: {e}")
            await callback.message.edit_text("Ошибка при добавлении.")
        finally:
            db.close()
    else:
        await callback.message.edit_text("Добавление отменено.")
    await state.finish()
    await callback.answer()


# ===== Редактирование и удаление — оставил без изменений =====
# (твой код редактирования останется, только кнопки skip будут ловиться)

async def list_user_cars(msg: types.Message, state: FSMContext):
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == msg.from_user.id).first()
    if not user:
        await msg.answer("Зарегистрируйтесь (/start).")
        return
    cars = db.query(Car).filter(Car.owner_id == user.id).all()
    db.close()
    if not cars:
        await msg.answer("Нет авто.")
        return

    markup = InlineKeyboardMarkup()
    for car in cars:
        markup.add(InlineKeyboardButton(
            f"{car.brand} {car.model} ({car.year})",
            callback_data=f"edit_select:{car.id}"
        ))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="cancel"))
    await msg.answer("Выберите авто для редактирования:", reply_markup=markup)
    await EditCarFSM.choose_car.set()


async def select_car_edit(callback: CallbackQuery, state: FSMContext):
    car_id = int(callback.data.split(":")[1])
    await state.update_data(edit_car_id=car_id)
    markup = InlineKeyboardMarkup(row_width=2)
    fields = ["Марка", "Модель", "Год", "Цена", "Скидка", "Условия", "Город", "Фото", "Удалить"]
    for f in fields:
        markup.insert(InlineKeyboardButton(f, callback_data=f"field:{f}"))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="cancel"))
    await callback.message.edit_text("Что изменить?", reply_markup=markup)
    await EditCarFSM.choose_field.set()


async def choose_field(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await cancel_handler(callback, state)
        return
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    if field == "Удалить":
        await callback.message.edit_text("Удалить авто? Да/Нет", reply_markup=kb_confirm())
        await EditCarFSM.confirm_delete.set()
        return
    elif field == "Фото":
        await callback.message.edit_text("📸 Отправьте новое фото или нажмите 'Пропустить':",
                                         reply_markup=kb_skip_cancel())
        await EditCarFSM.upload_photo.set();
        return

    await callback.message.edit_text(f"Введите новое значение для '{field}':", reply_markup=kb_back())
    await EditCarFSM.enter_value.set()


async def update_value(msg: types.Message, state: FSMContext):
    from handlers.menu import main_menu_kb
    d = await state.get_data()
    car_id = d["edit_car_id"]
    field = d["edit_field"]
    db = SessionLocal()
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        await msg.answer("Авто не найден.");
        await state.finish()
        db.close()
        return

    if field == "Фото":
        await msg.answer("Отправьте фото или 'Пропустить':", reply_markup=kb_skip_cancel())
        await AddCarFSM.photo.set()
        return

    val = msg.text
    try:
        if field == "Год":
            val = int(val)
        elif field in ("Цена", "Скидка"):
            val = float(val.replace(",", "."))
        setattr(car, {"Марка": "brand",
                      "Модель": "model",
                      "Год": "year",
                      "Цена": "price_per_day",
                      "Скидка": "discount",
                      "Условия": "rental_terms",
                      "Город": "city"}
        [field], val)
        db.commit()
        await msg.answer("✅ Обновлено.", reply_markup=main_menu_kb())
    except Exception as e:
        logger.error(e)
        await msg.answer("Ошибка при обновлении.")
    finally:
        db.close()
        await state.finish()


async def edit_upload_photo(msg: types.Message, state: FSMContext):
    from handlers.menu import main_menu_kb
    d = await state.get_data()
    car_id = d.get("edit_car_id")

    db = SessionLocal()
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        await msg.answer("Авто не найдено.");
        await state.finish();
        db.close();
        return

    if msg.photo:
        car.photo_file_id = msg.photo[-1].file_id
        db.commit()
        await msg.answer("✅ Фото обновлено.", reply_markup=main_menu_kb())

    elif msg.text.lower() == "пропустить":
        car.photo_file_id = None
        db.commit()
        await msg.answer("✅ Фото удалено.", reply_markup=main_menu_kb())

    else:
        await msg.answer("Отправьте изображение или нажмите 'Пропустить'.", reply_markup=kb_skip_cancel())
        db.close();
        return

    db.close()
    await state.finish()


async def confirm_delete_car(callback: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    car_id = d.get("edit_car_id")
    db = SessionLocal()
    car = db.query(Car).filter(Car.id == car_id).first()
    if callback.data == "confirm_yes" and car:
        db.delete(car)
        db.commit()
        await callback.message.edit_text("Удалено 👍")
    else:
        await callback.message.edit_text("Удаление отменено.")
    db.close()
    await state.finish()
    await callback.answer()


def register_cars_handlers(dp: Dispatcher):
    dp.register_message_handler(get_brand, state=AddCarFSM.brand)
    dp.register_message_handler(get_model, state=AddCarFSM.model)
    dp.register_message_handler(get_year, state=AddCarFSM.year)
    dp.register_message_handler(get_license, state=AddCarFSM.license_plate)
    dp.register_message_handler(get_vin, state=AddCarFSM.vin)
    dp.register_message_handler(get_price, state=AddCarFSM.price)
    dp.register_message_handler(get_discount, state=AddCarFSM.discount)
    dp.register_message_handler(get_terms, state=AddCarFSM.rental_terms)
    dp.register_message_handler(get_city, state=AddCarFSM.city)
    dp.register_message_handler(get_photo, content_types=["photo", "text"], state=AddCarFSM.photo)

    # Пропуски
    dp.register_callback_query_handler(skip_license, text="skip", state=AddCarFSM.license_plate)
    dp.register_callback_query_handler(skip_vin, text="skip", state=AddCarFSM.vin)
    dp.register_callback_query_handler(skip_terms, text="skip", state=AddCarFSM.rental_terms)
    dp.register_callback_query_handler(skip_photo, text="skip", state=AddCarFSM.photo)

    # Отмена и подтверждение
    dp.register_callback_query_handler(cancel_handler, text="cancel", state="*")
    dp.register_callback_query_handler(confirm_add, state=AddCarFSM.confirm)

    dp.register_callback_query_handler(select_car_edit, lambda c: c.data.startswith("edit_select:"),
                                       state=EditCarFSM.choose_car)
    dp.register_callback_query_handler(choose_field, state=EditCarFSM.choose_field)
    dp.register_message_handler(update_value, state=EditCarFSM.enter_value)
    dp.register_message_handler(edit_upload_photo, content_types=["photo", "text"], state=EditCarFSM.upload_photo)
    dp.register_callback_query_handler(confirm_delete_car, state=EditCarFSM.confirm_delete)
