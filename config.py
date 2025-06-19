import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "7994240662:AAHOHUfg5-6u76B-Jfe1Pey6k7AU8zPEqU8")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/myrentcar")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "your_stripe_secret_key")
FREKASSA_MERCHANT_ID = os.getenv("FREKASSA_MERCHANT_ID", "your_frekassa_merchant_id")
FREKASSA_SECRET = os.getenv("FREKASSA_SECRET", "your_frekassa_secret_key")

NBS_PRIMALAC = "ROMAN DAVYDOV PR IZNAJMLJIVANJE I LIZING AUTOMOBILA MY RENT CAR NOVI SAD"
NBS_BROJ_RACUNA = "190-0000000034540-60"