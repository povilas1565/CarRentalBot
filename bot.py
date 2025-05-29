import logging
from aiogram import Bot, Dispatcher
from aiogram.types import ParseMode
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import registration, cars, bookings, contracts, payments, reviews, calculator
from loguru import logger
import asyncio

logger.add("logs/bot.log", rotation="10 MB", compression="zip")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please set it in config.py or environment variables.")
        return

    # Инициализация бота и диспетчера с in-memory storage для состояний
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)

    # Регистрируем хендлеры, передавая Dispatcher
    registration.register_registration_handlers(dp)
    cars.register_cars_handlers(dp)
    bookings.register_bookings_handlers(dp)
    contracts.register_contracts_handlers(dp)
    payments.register_payments_handlers(dp)   # вот тут твои payments
    reviews.register_reviews_handlers(dp)      # и reviews

    logger.info("Bot started")

    # Запускаем поллинг
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())