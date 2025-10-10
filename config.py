import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8209248067:AAGjMQeIbnLHG3zUhKOL2g4luB8if-Ig4m4")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/myrentcar")
FREEKASSA_MERCHANT_ID = os.getenv("FREEKASSA_MERCHANT_ID", "your_fk_merchant_id")
FREEKASSA_SECRET_1 = os.getenv("FREEKASSA_SECRET_1", "your_fk_secret_word_1")  # для создания ссылок
FREEKASSA_SECRET_2 = os.getenv("FREEKASSA_SECRET_2", "your_fk_secret_word_2")  # для вебхука

NBS_PRIMALAC = "ROMAN DAVYDOV PR IZNAJMLJIVANJE I LIZING AUTOMOBILA MY RENT CAR NOVI SAD"
NBS_BROJ_RACUNA = "190-0000000034540-60"
