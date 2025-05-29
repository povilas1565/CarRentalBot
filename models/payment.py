from sqlalchemy import Column, Integer, ForeignKey, String, Float, Enum, DateTime
from database import Base
from sqlalchemy.orm import relationship
import enum
import datetime

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class PaymentMethod(enum.Enum):
    STRIPE = "stripe"
    FREKASSA = "freekassa"
    NBS_QR = "nbs_qr"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    method = Column(Enum(PaymentMethod), nullable=False)
    transaction_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    booking = relationship("Booking")