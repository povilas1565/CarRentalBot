from datetime import datetime

from pydantic_core.core_schema import nullable_schema
from sqlalchemy import Column, Integer, ForeignKey, Date, Enum, Float, Boolean, DateTime
from database import Base
from sqlalchemy.orm import relationship
import enum

class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"))
    renter_id = Column(Integer, ForeignKey("users.id"))
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    contract_signed = Column(Boolean, default=False)

    car = relationship("Car")
    renter = relationship("User")