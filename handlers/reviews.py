
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from sqlalchemy import func

from database import SessionLocal
from models.car import Car
from models.review import Review
from models.booking import Booking
from aiogram import Dispatcher

class ReviewStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()
    show_reviews = State()

async def start_review(message: types.Message, state: FSMContext):
    args = message.get_args()
    if not args or not args.isdigit():
        await message.answer("Пожалуйста, укажи ID бронирования для отзыва, например: /review 123")
        return
    booking_id = int(args)
    db = SessionLocal()
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        await message.answer("Бронирование не найдено.")
        db.close()
        return

    # Сохраняем car_id и renter_id для отзыва
    await state.update_data(booking_id=booking_id, car_id=booking.car_id, renter_id=booking.renter_id)
    await message.answer("Оцени аренду по шкале от 1 до 5 (можно с десятыми, например 4.5):")
    await ReviewStates.waiting_for_rating.set()
    db.close()

async def process_rating(message: types.Message, state: FSMContext):
    rating_text = message.text.strip().replace(',', '.')
    try:
        rating = float(rating_text)
        if not (1 <= rating <= 5):
            raise ValueError()
    except ValueError:
        await message.answer("Пожалуйста, введи число от 1.0 до 5.0.")
        return
    await state.update_data(rating=rating)
    await message.answer("Напиши отзыв или просто отправь 'пропустить':")
    await ReviewStates.waiting_for_comment.set()

async def process_comment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    car_id = data.get("car_id")
    renter_id = data.get("renter_id")
    rating = data.get("rating")
    comment = message.text.strip()
    if comment.lower() == "miss":
        comment = None

    db = SessionLocal()

    review = Review(
        car_id=car_id,
        renter_id=renter_id,
        rating=rating,
        comment=comment
    )
    db.add(review)
    db.commit()
    db.close()

    await message.answer("Спасибо за отзыв!")
    await state.finish()

async def show_reviews(message: types.Message):
    args = message.get_args()
    if not args or not args.isdigit():
        await message.answer("Пожалуйста, укажи ID автомобиля, например: /reviews 10")
        return
    car_id = int(args)

    db = SessionLocal()
    car = db.query(Car).filter(Car.id == car_id).first()
    if not car:
        await message.answer("Автомобиль не найден.")
        db.close()
        return

    reviews = db.query(Review).filter(Review.car_id == car_id).all()
    if not reviews:
        await message.answer(f"Отзывов для {car.model} пока нет.")
        db.close()
        return

    avg_rating = db.query(func.avg(Review.rating)).filter(Review.car_id == car_id).scalar()
    avg_rating = round(avg_rating, 2) if avg_rating else "нет"

    msg = f"Отзывы для {car.model} (средний рейтинг: {avg_rating}):\n\n"
    for r in reviews:
        commenter = f"Пользователь {r.renter_id}"
        rating = f"Оценка: {r.rating}"
        comment = r.comment if r.comment else "-"
        msg += f"{commenter}\n{rating}\nОтзыв: {comment}\n\n"

    db.close()
    await message.answer(msg)


def register_reviews_handlers(dp: Dispatcher):
    dp.register_message_handler(start_review, commands=["review"], state="*")
    dp.register_message_handler(process_rating, state=ReviewStates.waiting_for_rating)
    dp.register_message_handler(process_comment, state=ReviewStates.waiting_for_comment)
    dp.register_message_handler(show_reviews, commands=["reviews"], state="*")
    