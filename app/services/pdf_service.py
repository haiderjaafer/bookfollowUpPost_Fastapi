from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.PDFTable import PDFTable, PDFCreate



class PDFService:
    @staticmethod
    async def get_pdf_count(db: AsyncSession, book_id: int) -> int:
        """
        Returns the number of PDFs linked to the given book ID using SQL COUNT.
        """
        result = await db.execute(
            select(func.count()).select_from(PDFTable).where(PDFTable.bookID == book_id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_pdf_count_async(db: AsyncSession, book_id: int) -> int:
        """
        Returns the number of PDFs linked to the given book ID using scalars().
        """
        result = await db.execute(
            select(PDFTable).filter(PDFTable.bookID == book_id)
        )
        records = result.scalars().all()
        return len(records)

    @staticmethod
    async def insert_pdf(db: AsyncSession, pdf: PDFCreate) -> PDFTable:
        """
        Inserts a new PDF record into the database.
        """
        new_pdf = PDFTable(**pdf.model_dump())
        db.add(new_pdf)
        await db.commit()
        await db.refresh(new_pdf)
        return new_pdf

   