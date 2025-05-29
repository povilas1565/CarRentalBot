from sqlalchemy import Column, Integer, String, Boolean, Enum
from database import Base
import enum

class UserType(enum.Enum):
    OWNER_PHYSICAL = "owner_physical"
    OWNER_LEGAL = "owner_legal"
    RENTER = "renter"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    user_type = Column(Enum(UserType), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    company_inn = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    registered = Column(Boolean, default=False)