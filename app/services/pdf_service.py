
import logging
import os
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func,delete
from app.models.PDFTable import PDFTable, PDFCreate
from pathlib import Path
from app.database.config import settings

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    


    
    
    @staticmethod
    async def delete_pdf_record(db: AsyncSession, id: int, pdf_path: str) -> bool:
        """
        Deletes a PDFTable record by ID and removes the associated PDF file from the filesystem.

        Args:
            db: AsyncSession for database access
            id: The ID of the PDFTable record
            pdf_path: The file path of the PDF to delete

        Returns:
            bool: True if both record and file (if exists) are deleted, False otherwise
        """
        try:
            # Step 1: Validate file path to prevent directory traversal
            base_path = settings.PDF_UPLOAD_PATH  # e.g., D:\booksFollowUp\pdfDestination
            if not PDFService.is_safe_path(base_path, pdf_path):
                logger.error(f"Invalid file path: {pdf_path}")
                raise HTTPException(status_code=400, detail="Invalid file path")

            # Step 2: Find the PDFTable record by ID
            stmt = select(PDFTable).filter(PDFTable.id == id)
            result = await db.execute(stmt)
            pdf_record = result.scalars().first()

            if not pdf_record:
                logger.warning(f"No PDF record found for ID: {id}")
                return False

            # Step 3: Normalize paths for comparison
            requested_path = str(Path(pdf_path).resolve()).replace("/", "\\")
            stored_path = str(Path(pdf_record.pdf).resolve()).replace("/", "\\")

            # Verify the pdf path matches the record
            if stored_path != requested_path:
                logger.warning(f"PDF path mismatch: requested {requested_path}, found {stored_path}")
                return False

            # Step 4: Delete the record from PDFTable
            delete_stmt = delete(PDFTable).filter(PDFTable.id == id)
            await db.execute(delete_stmt)
            await db.commit()
            logger.debug(f"Deleted PDFTable record with ID: {id}")

            # Step 5: Delete the file from the filesystem
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
                logger.debug(f"Deleted PDF file from filesystem: {pdf_path}")
            else:
                logger.warning(f"PDF file not found on filesystem: {pdf_path}")
                # Return True since DB deletion succeeded
                return True

            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting PDF record or file: {str(e)}")
            await db.rollback()
            return False

    @staticmethod
    def is_safe_path(base_path: str, path: str) -> bool:
        """
        Ensures the file path is within the allowed directory to prevent directory traversal.

        Args:
            base_path: The base directory (e.g., D:\booksFollowUp\pdfDestination)
            path: The file path to check

        Returns:
            bool: True if the path is safe, False otherwise
        """
        try:
            base = Path(base_path).resolve()
            target = Path(path).resolve()
            return base in target.parents or base == target
        except Exception:
            return False