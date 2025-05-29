from sqlalchemy import Column, Integer, ForeignKey, String, Float
from database import Base
from sqlalchemy.orm import relationship

class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"))
    renter_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Float, nullable=False)
    comment = Column(String, nullable=True)

    car = relationship("Car")
    renter = relationship("User")