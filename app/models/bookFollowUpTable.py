from sqlalchemy import Column, Integer, String, Date, Unicode, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import List, Optional
from app.models.PDFTable import PDFResponse



class BookFollowUpTable(Base):
    __tablename__ = "bookFollowUpTable"

    id = Column(BigInteger, primary_key=True, index=True)  # Changed to BigInteger
    bookType = Column(Unicode(10), nullable=True)
    bookNo = Column(Unicode, nullable=True)  # Changed to Unicode(max)
    bookDate = Column(Date, nullable=True)
    directoryName = Column(Unicode, nullable=True)
    incomingNo = Column(Unicode, nullable=True)  # Fixed case and changed to Unicode(max)
    incomingDate = Column(Date, nullable=True)   # Fixed case
    subject = Column(Unicode, nullable=True)
    destination = Column(Unicode, nullable=True)
    bookAction = Column(Unicode, nullable=True)
    bookStatus = Column(Unicode, nullable=True)
    notes = Column(Unicode, nullable=True)
    userID = Column(String(10), nullable=True)  # Changed to String as per DB schema
    currentDate = Column(Date, nullable=True)
    junctionID = Column(BigInteger, ForeignKey('committee_departments_junction.id'), nullable=True)  # New field

    # Relationships
    junction = relationship("CommitteeDepartmentsJunction", back_populates="books")
    bridge_records = relationship("BookJunctionBridge", back_populates="book")


class CommitteeDepartmentsJunction(Base):
    __tablename__ = "committee_departments_junction"

    id = Column(BigInteger, primary_key=True, index=True)
    coID = Column(BigInteger, ForeignKey('committees.coID'), nullable=False)
    deID = Column(Integer, ForeignKey('departments.deID'), nullable=False)

    # Relationships
    committee = relationship("Committee", back_populates="department_junctions")
    department = relationship("Department", back_populates="committee_junctions")
    books = relationship("BookFollowUpTable", back_populates="junction")
    bridge_records = relationship("BookJunctionBridge", back_populates="junction")

    # Unique constraint is handled at database level


class BookJunctionBridge(Base):
    __tablename__ = "book_junction_bridge"

    id = Column(BigInteger, primary_key=True, index=True)
    bookID = Column(BigInteger, ForeignKey('bookFollowUpTable.id'), nullable=False)
    junctionID = Column(BigInteger, ForeignKey('committee_departments_junction.id'), nullable=False)

    # Relationships
    book = relationship("BookFollowUpTable", back_populates="bridge_records")
    junction = relationship("CommitteeDepartmentsJunction", back_populates="bridge_records")

    # Unique constraint is handled at database level







# class BookFollowUpCreate(BaseModel):
#     bookType: Optional[str] = None
#     bookNo: Optional[str] = None
#     bookDate: Optional[str] = None
#     directoryName: Optional[str] = None
#     deID:Optional[int] = None
#     incomingNo: Optional[str] = None
#     incomingDate: Optional[str] = None
#     subject: Optional[str] = None
#     destination: Optional[str] = None
#     bookAction: Optional[str] = None
#     bookStatus: Optional[str] = None
#     notes: Optional[str] = None
#     currentDate: Optional[str] = None
#     userID: Optional[int] = None

#     @field_validator('bookDate', 'incomingDate', 'currentDate')
#     def validate_date(cls, value):
#         if value is None:
#             return None
#         if isinstance(value, str):
#             try:
#                 datetime.strptime(value, '%Y-%m-%d')
#                 return value
#             except ValueError:
#                 raise ValueError(f"Invalid date format for {value}; expected YYYY-MM-DD")
#         elif isinstance(value, date):
#             return value.strftime('%Y-%m-%d')
#         raise ValueError(f"Invalid date type for {value}; expected string or date")

#     class Config:
#         from_attributes = True


# Update your existing BookFollowUpResponse model
class BookFollowUpResponse(BaseModel):
    serialNo: Optional[int] = None  
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
    
    # Primary committee/department
    coID: Optional[int] = None
    Com: Optional[str] = None
    deID: Optional[str] = None
    departmentName: Optional[str] = None
    
    # Multi-department fields - ADD THESE
    all_departments: List[dict] = []
    department_names: Optional[str] = None
    department_count: Optional[int] = 0
    
    countOfLateBooks: Optional[int] = None
    len: Optional[int] = None
    
    class Config:
        from_attributes = True





class PaginatedOrderOut(BaseModel):
    data: List[BookFollowUpResponse]
    total: int
    page: int
    limit: int
    totalPages: int



# Updated Pydantic Model for Multi-Department Response
class BookFollowUpWithPDFResponseForUpdateByBookID(BaseModel):
    id: int
    bookType: Optional[str] = None
    bookNo: Optional[str] = None
    bookDate: Optional[str] = None
    directoryName: Optional[str] = None
    junctionID: Optional[int] = None  # Added junction reference
    
    # Primary department/committee info (from junctionID)
    coID: Optional[int] = None
    deID: Optional[int] = None
    Com: Optional[str] = None  # Committee name
    departmentName: Optional[str] = None  # Department name
    
    # Multi-department info
    all_departments: List[dict] = []  # All associated departments
    department_names: Optional[str] = None  # Comma-separated names
    department_count: int = 0
    
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


# Response models for type safety
class BookTypeCounts(BaseModel):
    External: int
    Internal: int
    Fax: int

class BookStatusCounts(BaseModel):
    Accomplished: int
    Pending: int
    Deliberation: int

class UserBookCount(BaseModel):
    username: str
    bookCount: int

class SubjectRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500, description="Subject to search for")
    
# Enhanced Response Model with Junction Details
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
    junctionID: Optional[int] = None

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


class BookFollowUpMultiDepartmentResponse(BaseModel):
    id: int
    bookType: Optional[str] = None
    bookNo: Optional[str] = None
    bookDate: Optional[date] = None
    subject: Optional[str] = None
    bookStatus: Optional[str] = None
    committee_id: int
    committee_name: Optional[str] = None
    departments: List[dict] = []  # [{"deID": 11, "departmentName": "Finance"}, ...]
    total_departments: int = 0

    class Config:
        from_attributes = True



# Updated Pydantic Model for JSON Updates with Multi-Department Support
class BookFollowUpUpdate(BaseModel):
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
    userID: Optional[int] = None
    
    # Multi-department fields
    coID: Optional[int] = None  # Committee ID
    deIDs: Optional[str] = None  # Comma-separated department IDs or JSON array string

    @field_validator('bookDate', 'incomingDate')
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