from typing import Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String
from app.database.database import Base


class Department(Base):
    __tablename__ = "departments"

    deID = Column(Integer, primary_key=True, autoincrement=True)
    departmentName = Column(String(250), nullable=True)
    coID = Column(Integer, nullable=True)  # References committees.coID




# Pydantic model for Department response (single departmentName)
class DepartmentNameResponse(BaseModel):
    departmentName: Optional[str] = None

    class Config:
        from_attributes = True