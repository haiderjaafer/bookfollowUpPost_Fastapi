from app.database.database import Base
from sqlalchemy import BigInteger, Column, Integer, String
from pydantic import BaseModel
from typing import  Optional
from sqlalchemy.orm import relationship


class Committee(Base):
    __tablename__ = "committees"
    
    coID = Column(BigInteger, primary_key=True, index=True)  # Assuming this is BigInteger now
    Com = Column(String(255), nullable=True)
    # ... other existing fields

    # Add new relationship
    department_junctions = relationship("CommitteeDepartmentsJunction", back_populates="committee")


# Pydantic model for Committee response
class CommitteeResponse(BaseModel):
    coID: int
    Com: Optional[str] = None

    class Config:
        from_attributes = True  # Allow mapping from SQLAlchemy ORM objects    