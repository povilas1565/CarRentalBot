import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import ParseMode
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import Base, engine
from handlers import registration, cars, bookings, contracts, payments, reviews, calculator, menu
from loguru import logger

from fastapi import FastAPI
from api.webhook import app as webhook_app
import uvicorn

# Создаём таблицы (один раз)
print("Creating tables...")
Base.metadata.create_all(bind=engine)

logger.add("logs/bot.log", rotation="10 MB", compression="zip")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please set it in config.py or environment variables.")
        return

    # Создаём бота и диспетчер
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)

    # Регистрируем все хендлеры
    registration.register_registration_handlers(dp)
    cars.register_cars_handlers(dp)
    bookings.register_bookings_handlers(dp)
    contracts.register_contracts_handlers(dp)
    payments.register_payments_handlers(dp)
    reviews.register_reviews_handlers(dp)
    menu.register_menu_handlers(dp)  # <-- регистрируем меню

    fastapi_app = FastAPI()

    # Монтируем вебхук роутер
    fastapi_app.mount("/api", webhook_app)

    # Запускаем FastAPI сервер асинхронно
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    # Запускаем вебсервер в фоне
    loop = asyncio.get_running_loop()
    loop.create_task(server.serve())

    logger.info("Bot started with FastAPI webhook server on port 8000")

    # Запускаем Telegram polling
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())