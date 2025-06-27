from fastapi import FastAPI, Request, Response
import hashlib
from database import SessionLocal
from models.payment import Payment, PaymentStatus

app = FastAPI()

FREEKASSA_SECRET_2 = "HdatG]bYxMkJ4IT" # Секретный ключ для проверки подписи

@app.post("/api/freekassa_webhook")
async def freekassa_webhook(request: Request):
    form = await request.form()

    # Получаем необходимые параметры из Freekassa
    out_summ = form.get("OutSum")
    inv_id = form.get("InvId")
    signature = form.get("SignatureValue")
    payment_status = form.get("PaymentStatus")  # если есть

    # Проверка подписи
    crc_str = f"{out_summ}:{inv_id}:{FREEKASSA_SECRET_2}"
    expected_signature = hashlib.md5(crc_str.encode("utf-8")).hexdigest().upper()

    if expected_signature != signature.upper():
        return Response(content="bad sign", status_code=400)

    # Обновляем статус оплаты в базе
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == int(inv_id)).first()
        if not payment:
            return Response(content="payment not found", status_code=404)

        payment.status = PaymentStatus.PAID  # или нужный статус
        db.commit()
    finally:
        db.close()

    return Response(content="OK", status_code=200)
