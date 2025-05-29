from sqlalchemy import Column, Integer, ForeignKey, String, Date, Boolean
from database import Base
from sqlalchemy.orm import relationship

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"))
    contract_pdf_path = Column(String, nullable=True)
    signed = Column(Boolean, default=False)
    signature_data = Column(String, nullable=True)

    booking = relationship("Booking")
