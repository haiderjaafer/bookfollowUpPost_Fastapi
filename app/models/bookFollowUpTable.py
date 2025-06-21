from sqlalchemy import Column, Integer, String, Date,Unicode
from app.database.database import Base


from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import List, Optional

from app.models.PDFTable import PDFResponse


class BookFollowUpTable(Base):
    __tablename__ = "bookFollowUpTable"

    id = Column(Integer, primary_key=True, index=True)
    bookType = Column(Unicode(20), nullable=True)
    bookNo = Column(String(10), nullable=True)
    bookDate = Column(Date, nullable=True)
    directoryName = Column(Unicode, nullable=True)
    incomingNo = Column(String(10), nullable=True)   # fix IncomingNo with sql table
    incomingDate = Column(Date, nullable=True)       # fix IncomingDate with sql table
    subject = Column(Unicode(500), nullable=True)
    destination = Column(Unicode(300), nullable=True)
    bookAction = Column(Unicode(500), nullable=True)
    bookStatus = Column(Unicode(20), nullable=True)
    notes = Column(Unicode(500), nullable=True)
    currentDate = Column(Date, nullable=True)
    userID = Column(Integer, nullable=True)






class BookFollowUpCreate(BaseModel):
    bookType: Optional[str] = None
    bookNo: Optional[str] = None
    bookDate: Optional[str] = None
    directoryName: Optional[str] = None
    incomingNo: Optional[str] = None
    incomingDate: Optional[str] = None
    subject: Optional[str] = None
    destination: Optional[str] = None
    bookAction: Optional[str] = None
    bookStatus: Optional[str] = None
    notes: Optional[str] = None
    currentDate: Optional[str] = None
    userID: Optional[int] = None

    @field_validator('bookDate', 'incomingDate', 'currentDate')
    def validate_date(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                datetime.strptime(value, '%Y-%m-%d')
                return value
            except ValueError:
                raise ValueError(f"Invalid date format for {value}; expected YYYY-MM-DD")
        elif isinstance(value, date):
            return value.strftime('%Y-%m-%d')
        raise ValueError(f"Invalid date type for {value}; expected string or date")

    class Config:
        from_attributes = True

class BookFollowUpResponse(BaseModel):
    id: int
    bookType: Optional[str]= None
    bookNo: Optional[str]= None
    bookDate: Optional[date]= None
    directoryName: Optional[str]= None
    incomingNo: Optional[str]= None
    incomingDate: Optional[date]= None
    subject: Optional[str]= None
    destination: Optional[str]= None
    bookAction: Optional[str]= None
    bookStatus: Optional[str]= None
    notes: Optional[str]= None
    currentDate: Optional[str]= None
    userID: Optional[int]= None
    countOfLateBooks: Optional[int]= None 

    class Config:
        from_attributes = True



class PaginatedOrderOut(BaseModel):
    data: List[BookFollowUpResponse]
    total: int
    page: int
    limit: int
    totalPages: int



class BookFollowUpWithPDFResponseForUpdateByBookID(BaseModel):
    id: int
    bookType: Optional[str] = None
    bookNo: Optional[str] = None
    bookDate: Optional[str] = None
    directoryName: Optional[str] = None
    incomingNo: Optional[str] = None
    incomingDate: Optional[str] = None
    subject: Optional[str] = None
    destination: Optional[str] = None
    bookAction: Optional[str] = None
    bookStatus: Optional[str] = None
    notes: Optional[str] = None
    currentDate: Optional[str] = None
    userID: Optional[int] = None
    username: Optional[str] = None
    countOfPDFs: Optional[int] = None
    pdfFiles: List[PDFResponse] = []

    @field_validator('bookDate', 'incomingDate', 'currentDate')
    def validate_date(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                datetime.strptime(value, '%Y-%m-%d')
                return value
            except ValueError:
                raise ValueError(f"Invalid date format for {value}; expected YYYY-MM-DD")
        elif isinstance(value, date):
            return value.strftime('%Y-%m-%d')
        raise ValueError(f"Invalid date type for {value}; expected string or date")

    class Config:
        from_attributes = True


