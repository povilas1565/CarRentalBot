import hashlib
from fastapi import FastAPI, Request, Form, HTTPException
from database import SessionLocal
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.booking import Booking, BookingStatus
from loguru import logger

from config import FREEKASSA_SECRET_2

app = FastAPI()


@app.post("/freekassa_callback")
async def freekassa_callback(
        MERCHANT_ID: str = Form(...),
        AMOUNT: str = Form(...),
        intid: str = Form(...),
        MERCHANT_ORDER_ID: str = Form(...),
        SIGN: str = Form(...),
):
    sign_str = f"{MERCHANT_ID}:{AMOUNT}:{FREEKASSA_SECRET_2}:{MERCHANT_ORDER_ID}"
    expected_sign = hashlib.md5(sign_str.encode()).hexdigest()

    if expected_sign != SIGN:
        logger.warning("FreeKassa: invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(
            Payment.id == int(MERCHANT_ORDER_ID),
            Payment.method == PaymentMethod.FREEKASSA
        ).first()

        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        payment.status = PaymentStatus.COMPLETED
        payment.transaction_id = intid

        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
        if booking:
            booking.status = BookingStatus.CONFIRMED

        db.commit()
        logger.info(f"Payment {payment.id} completed via FreeKassa")
        return "YES"
    except Exception as e:
        logger.error(f"FreeKassa error: {e}")
        raise HTTPException(status_code=500, detail="Internal Error")
    finally:
        db.close()


@app.get("/payment_success")
async def payment_success():
    return "<html><body><h1>Оплата прошла успешно!</h1><p>Спасибо, что воспользовались нашим сервисом.</p></body></html>"


@app.get("/payment_fail")
async def payment_fail():
    return "<html><body><h1>Оплата не прошла.</h1><p>Пожалуйста, попробуйте снова или свяжитесь с поддержкой.</p></body></html>"