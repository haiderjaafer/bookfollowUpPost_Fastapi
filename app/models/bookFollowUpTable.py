from sqlalchemy import Column, Integer, String, Date,Unicode
from app.database.database import Base


from pydantic import BaseModel
from datetime import date
from typing import Optional


class BookFollowUpTable(Base):
    __tablename__ = "bookFollowUpTable"

    id = Column(Integer, primary_key=True, index=True)
    bookType = Column(Unicode(20), nullable=True)
    bookNo = Column(String(10), nullable=True)
    bookDate = Column(Date, nullable=True)
    directoryName = Column(Unicode, nullable=True)
    incomingNo = Column(String(10), nullable=True)
    incomingDate = Column(Date, nullable=True)
    subject = Column(Unicode(500), nullable=True)
    destination = Column(Unicode(300), nullable=True)
    bookAction = Column(Unicode(500), nullable=True)
    bookStatus = Column(Unicode(20), nullable=True)
    notes = Column(Unicode(500), nullable=True)
    currentDate = Column(Date, nullable=True)
    userID = Column(Integer, nullable=True)






class BookFollowUpCreate(BaseModel):
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
   # currentDate: Optional[date]= None
    userID: Optional[int]= None


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
    #currentDate: Optional[date]= None
    userID: Optional[int]= None

    class Config:
        orm_mode = True
