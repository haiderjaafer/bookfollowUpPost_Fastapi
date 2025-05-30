from sqlalchemy import Column, Integer, String, Date, ForeignKey
#from sqlalchemy.orm import relationship
from app.database.database import Base

from pydantic import BaseModel
from typing import Optional
from datetime import date

class PDFTable(Base):
    __tablename__ = "PDFTable"

    id = Column(Integer, primary_key=True, index=True)
    bookID = Column(Integer,  nullable=True)
    bookNo = Column(String(50), nullable=True)
    countPdf = Column(Integer, nullable=True)
    pdf = Column(String, nullable=True)  # Stores PDF file path or URL
    userID = Column(Integer, nullable=True)
    currentDate = Column(Date, nullable=True)






class PDFCreate(BaseModel):
    bookID: Optional[int]
    bookNo: Optional[str]
    countPdf: Optional[int]
    pdf: Optional[str]
    userID: Optional[int]
    currentDate: Optional[date]


class PDFResponse(PDFCreate):
    id: int
    currentDate: date

    class Config:
        from_attributes = True
