import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/myrentcar")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "your_stripe_secret_key")
FREKASSA_MERCHANT_ID = os.getenv("FREKASSA_MERCHANT_ID", "your_frekassa_merchant_id")
FREKASSA_SECRET = os.getenv("FREKASSA_SECRET", "your_frekassa_secret_key")

NBS_ACCOUNT_NUMBER = "190-0000000034540-60"
NBS_RECIPIENT_NAME = "ROMAN DAVYDOV PR"