from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.PDFTable import PDFTable, PDFCreate


class PDFService:
    @staticmethod
    async def get_pdf_count(db: AsyncSession, book_id: int) -> int:
        result = await db.execute(
            select(func.count()).select_from(PDFTable).where(PDFTable.bookID == book_id)
        )
        return result.scalar_one()

    @staticmethod
    async def insert_pdf(db: AsyncSession, pdf: PDFCreate) -> None:
        new_pdf = PDFTable(**pdf.model_dump())
        db.add(new_pdf)
        await db.commit()
        await db.refresh(new_pdf)
