import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "7601278255:AAFFbnzm3fZEcOPfmJ2tbsXFHnv1h4YfYFI")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:root@localhost:5432/myrentcar")
PAYOP_WEBHOOK_SECRET = "your_payop_webhook_secret"
PAYOP_MERCHANT_ID = "your_payop_merchant_id"
PAYOP_API_KEY = "your_payop_api_key"
PAYOP_API_URL = "https://payop.com/api/v1/invoices"
PUBLIC_URL = "https://xx.xx.xx.xx/api"

NBS_PRIMALAC = "ROMAN DAVYDOV PR IZNAJMLJIVANJE I LIZING AUTOMOBILA MY RENT CAR NOVI SAD"
NBS_BROJ_RACUNA = "190-0000000034540-60"