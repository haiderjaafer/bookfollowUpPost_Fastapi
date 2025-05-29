from sqlalchemy.orm import Session
from app.models.PDFTable import PDFTable, PDFCreate

class PDFService:
    @staticmethod
    def get_pdf_count(db: Session, book_id: int) -> int:
        return db.query(PDFTable).filter(PDFTable.bookID == book_id).count()

    @staticmethod
    def insert_pdf(db: Session, pdf: PDFCreate) -> None:
        new_pdf = PDFTable(**pdf.model_dump())
        db.add(new_pdf)
        db.commit()
        db.refresh(new_pdf)
