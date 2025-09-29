from typing import Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import BigInteger, Column, Integer, String
from app.database.database import Base
from sqlalchemy.orm import relationship


class Department(Base):
    __tablename__ = "departments"
    
    deID = Column(Integer, primary_key=True, index=True)
    departmentName = Column(String(255), nullable=True)
    coID = Column(BigInteger, nullable=True)  # If this references committees
    # ... other existing fields

    # Add new relationship
    committee_junctions = relationship("CommitteeDepartmentsJunction", back_populates="department")



# Pydantic model for Department response (single departmentName)
class DepartmentNameResponse(BaseModel):
    deID: int
    departmentName: Optional[str] = None
    class Config:
        from_attributes = True