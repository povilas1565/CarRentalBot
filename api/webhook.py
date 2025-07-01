import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse
from database import SessionLocal
from models.payment import Payment, PaymentStatus, PaymentMethod
from models.booking import Booking, BookingStatus
from loguru import logger

from config import (
   PAYOP_WEBHOOK_SECRET
)

app = FastAPI()

@app.post("/payop_callback")
async def payop_callback(
        request: Request,
        x_signature: str = Header(None),  # уточни имя заголовка у PayOp
):
    body_bytes = await request.body()
    logger.info(f"Received PayOp callback raw body: {body_bytes}")

    # Проверка подписи
    if x_signature is None:
        logger.error("Missing X-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    computed_hmac = hmac.new(
        PAYOP_WEBHOOK_SECRET.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hmac, x_signature):
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    data = await request.json()
    logger.info(f"PayOp callback payload: {data}")

    order_id = data.get("order_id") or data.get("order")  # на всякий случай проверяем оба варианта
    status = data.get("status")
    transaction_id = data.get("transaction_id")

    if not order_id or not status:
        logger.error("Missing order_id or status in PayOp callback")
        raise HTTPException(status_code=400, detail="Missing order_id or status")

    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(
            Payment.id == int(order_id),
            Payment.method == PaymentMethod.PAYOP
        ).first()
        if not payment:
            logger.error(f"Payment with id {order_id} not found")
            raise HTTPException(status_code=404, detail="Payment not found")

        status_lower = status.lower()
        if status_lower in ("paid", "success"):
            payment.status = PaymentStatus.COMPLETED
            booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
            if booking:
                booking.status = BookingStatus.CONFIRMED
            logger.info(f"Payment {order_id} marked as COMPLETED")
        elif status_lower in ("failed", "fail"):
            payment.status = PaymentStatus.FAILED
            booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
            if booking:
                booking.status = BookingStatus.PENDING
            logger.info(f"Payment {order_id} marked as FAILED")
        elif status_lower == "cancel":
            payment.status = PaymentStatus.CANCELLED
            logger.info(f"Payment {order_id} marked as CANCELLED")
        else:
            payment.status = PaymentStatus.PENDING
            logger.warning(f"Received unknown payment status: {status}")

        payment.transaction_id = transaction_id
        db.commit()

        # Здесь можно уведомить пользователя в боте (нужен объект bot, можно через background task)
        # await bot.send_message(payment.user_id, f"Статус платежа обновлен: {payment.status}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing PayOp callback: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    finally:
        db.close()


@app.get("/payment_success", response_class=HTMLResponse)
async def payment_success():
    return "<html><body><h1>Оплата прошла успешно!</h1><p>Спасибо, что воспользовались нашим сервисом.</p></body></html>"


@app.get("/payment_fail", response_class=HTMLResponse)
async def payment_fail():
    return "<html><body><h1>Оплата не прошла.</h1><p>Пожалуйста, попробуйте снова или свяжитесь с поддержкой.</p></body></html>"