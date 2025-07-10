from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from database import Base
from sqlalchemy.orm import relationship

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    license_plate = Column(String, nullable=True)
    vin = Column(String, nullable=True)
    price_per_day = Column(Float, nullable=False)
    city = Column(String, nullable=False)  
    photo_file_id = Column(String, nullable=True)  
    rental_terms = Column(String, nullable=True)
    available = Column(Boolean, default=True)
    discount = Column(Float, default=0.0) 

    owner = relationship("User", backref="cars")