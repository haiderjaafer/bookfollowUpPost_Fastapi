from datetime import datetime
from sqlalchemy.orm import Session
from app.models.bookFollowUpTable import BookFollowUpTable
from app.models.bookFollowUpTable import BookFollowUpCreate

class BookFollowUpClass:
    
    @staticmethod
    def create_book_follow_up(db: Session, book_data: BookFollowUpCreate) -> BookFollowUpTable:
        new_record = BookFollowUpTable(
            bookType=book_data.bookType,
            bookNo=book_data.bookNo,
            bookDate=book_data.bookDate,
            directoryName=book_data.directoryName,
            IncomingNo=book_data.IncomingNo,
            IncomingDate=book_data.IncomingDate,
            subject=book_data.subject,
            destination=book_data.destination,
            bookAction=book_data.bookAction,
            bookStatus=book_data.bookStatus,
            notes=book_data.notes,
            currentDate=datetime.now().date(),
            userID=book_data.userID
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return new_record
