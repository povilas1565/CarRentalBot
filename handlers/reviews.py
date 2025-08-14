from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from sqlalchemy import func

from database import SessionLocal
from keyboards.inline import cancel_kb, comment_kb
from models.car import Car
from models.review import Review
from models.booking import Booking
from handlers.menu import main_menu_kb


class ReviewStates(StatesGroup):
    waiting_for_booking_id = State()
    waiting_for_rating = State()
    waiting_for_comment = State()
    waiting_for_car_id = State()


# ⬇️ Старт добавления отзыва
async def review_start_handler(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Введите ID бронирования, чтобы оставить отзыв:",
        reply_markup=cancel_kb()
    )
    await ReviewStates.waiting_for_booking_id.set()
    await callback.answer()


# ⬇️ Обработка ID бронирования
async def process_booking_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте снова:", reply_markup=cancel_kb())
        return

    booking_id = int(message.text)
    db = SessionLocal()
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    db.close()

    if not booking:
        await message.answer("Бронирование не найдено. Попробуйте снова:", reply_markup=cancel_kb())
        return

    await state.update_data(
        booking_id=booking_id,
        car_id=booking.car_id,
        renter_id=booking.renter_id
    )
    await message.answer(
        "Оцени аренду от 1 до 5 (например 4.5):",
        reply_markup=cancel_kb()
    )
    await ReviewStates.waiting_for_rating.set()


# ⬇️ Обработка рейтинга
async def process_rating(message: types.Message, state: FSMContext):
    try:
        rating = float(message.text.strip().replace(',', '.'))
        if not (1 <= rating <= 5):
            raise ValueError()
    except ValueError:
        await message.answer("Введите число от 1.0 до 5.0:", reply_markup=cancel_kb())
        return

    await state.update_data(rating=rating)
    await message.answer(
        "Напишите отзыв или нажмите 'Пропустить':",
        reply_markup=comment_kb()
    )
    await ReviewStates.waiting_for_comment.set()


# ⬇️ Обработка комментария
async def process_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    comment = message.text.strip() or None

    db = SessionLocal()
    db.add(Review(
        car_id=data["car_id"],
        renter_id=data["renter_id"],
        rating=data["rating"],
        comment=comment
    ))
    db.commit()
    db.close()

    await message.answer("Спасибо за отзыв! 🙌", reply_markup=main_menu_kb())
    await state.finish()


# ⬇️ Пропуск комментария
async def skip_comment_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    db = SessionLocal()
    db.add(Review(
        car_id=data["car_id"],
        renter_id=data["renter_id"],
        rating=data["rating"],
        comment=None
    ))
    db.commit()
    db.close()

    await callback.message.edit_text("Спасибо за отзыв! 🙌", reply_markup=main_menu_kb())
    await state.finish()
    await callback.answer()


# ⬇️ Отмена действия
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("Действие отменено.", reply_markup=main_menu_kb())
    await callback.answer()


# ⬇️ Старт просмотра отзывов
async def show_reviews_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Введите ID автомобиля для просмотра отзывов:",
        reply_markup=cancel_kb()
    )
    await ReviewStates.waiting_for_car_id.set()
    await callback.answer()


# ⬇️ Обработка ID авто для просмотра
async def process_car_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте снова:", reply_markup=cancel_kb())
        return

    car_id = int(message.text)
    db = SessionLocal()
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        db.close()
        await message.answer("Авто не найдено. Попробуйте снова:", reply_markup=cancel_kb())
        return

    reviews = db.query(Review).filter(Review.car_id == car_id).all()
    avg_rating = db.query(func.avg(Review.rating)).filter(Review.car_id == car_id).scalar()
    db.close()

    if not reviews:
        await message.answer(f"Для {car.model} ещё нет отзывов.", reply_markup=main_menu_kb())
        await state.finish()
        return

    avg_text = f"{round(avg_rating, 2):.2f}" if avg_rating else "нет данных"
    msg = f"Отзывы для {car.model} (средний рейтинг: {avg_text}):\n\n"
    for r in reviews:
        msg += f"👤 Пользователь {r.renter_id}\n⭐️ {r.rating}\n💬 {r.comment or '—'}\n\n"

    await message.answer(msg, reply_markup=main_menu_kb())
    await state.finish()


# ⬇️ Регистрация хендлеров
def register_reviews_handlers(dp: Dispatcher):
    dp.register_callback_query_handler(review_start_handler, lambda c: c.data == "cmd_review", state="*")
    dp.register_callback_query_handler(show_reviews_start, lambda c: c.data == "cmd_reviews", state="*")

    dp.register_message_handler(process_booking_id, state=ReviewStates.waiting_for_booking_id)
    dp.register_message_handler(process_rating, state=ReviewStates.waiting_for_rating)
    dp.register_message_handler(process_comment, state=ReviewStates.waiting_for_comment)
    dp.register_message_handler(process_car_id, state=ReviewStates.waiting_for_car_id)

    dp.register_callback_query_handler(skip_comment_callback, lambda c: c.data == "skip_comment",
                                       state=ReviewStates.waiting_for_comment)
    dp.register_callback_query_handler(cancel_callback, lambda c: c.data == "cancel", state="*")
