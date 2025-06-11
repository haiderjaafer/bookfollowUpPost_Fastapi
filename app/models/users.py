from app.database.database import Base
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel

from typing import  Optional

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=True)
    password = Column(String(50), nullable=True)
    permission = Column(String(10), nullable=True)

class UserCreate(BaseModel):
    username: Optional[str]
    password: Optional[str]
    permission: Optional[str]

class UserResponse(BaseModel):
    id: int
    username: Optional[str]
    permission: Optional[str]  # Included for future use, excluding password for security

    class Config:
        from_attributes = True