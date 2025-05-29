from datetime import datetime
from sqlalchemy.orm import Session
from app.models.bookFollowUpTable import BookFollowUpTable
from app.models.bookFollowUpTable import BookFollowUpCreate
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date


from sqlalchemy.orm import Session
from app.models.bookFollowUpTable import BookFollowUpTable, BookFollowUpCreate

class BookFollowUpService:
    @staticmethod
    def insert_book(db: Session, book: BookFollowUpCreate) -> int:
        new_book = BookFollowUpTable(**book.model_dump())
        db.add(new_book)
        db.commit()
        db.refresh(new_book)
        return new_book.id

