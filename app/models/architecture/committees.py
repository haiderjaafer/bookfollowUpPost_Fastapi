from app.database.database import Base
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel
from typing import  Optional

class Committee(Base):
    __tablename__ = "committees"

    coID = Column(Integer, primary_key=True, autoincrement=True)
    Com = Column(String(255), nullable=True)


# Pydantic model for Committee response
class CommitteeResponse(BaseModel):
    coID: int
    Com: Optional[str] = None

    class Config:
        from_attributes = True  # Allow mapping from SQLAlchemy ORM objects    