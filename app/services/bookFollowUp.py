from datetime import date, datetime
import os
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.helper.save_pdf import save_pdf_to_server
from app.models.PDFTable import PDFCreate, PDFResponse, PDFTable
from app.models.bookFollowUpTable import BookFollowUpResponse, BookFollowUpTable, BookFollowUpCreate, BookFollowUpWithPDFResponseForUpdateByBookID
from sqlalchemy import select,func
from fastapi import HTTPException, Request, UploadFile
from app.models.users import Users
from app.services.pdf_service import PDFService
from app.database.config import settings

import logging

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:  # Avoid duplicate handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )



class BookFollowUpService:
    @staticmethod
    async def insert_book(db: AsyncSession, book: BookFollowUpCreate) -> int:
        new_book = BookFollowUpTable(**book.model_dump())
        db.add(new_book)
        await db.commit()
        await db.refresh(new_book)
        return new_book.id
    
    
    @staticmethod
    async def getAllBooksNo(db: AsyncSession):
            print("getAllBooksNo ... method")
            stmt = (
                select(BookFollowUpTable.bookNo)
                .group_by(BookFollowUpTable.bookNo)
                .order_by(BookFollowUpTable.bookNo)
            )
            result = await db.execute(stmt)
            return result.scalars().all()

    
    
    @staticmethod
    async def getAllIncomingNo(db: AsyncSession):
        stmt = (
            select(BookFollowUpTable.incomingNo)
            .where(BookFollowUpTable.incomingNo.isnot(None))   ## only return non-null incomingNo values
            .group_by(BookFollowUpTable.incomingNo)
            .order_by(BookFollowUpTable.incomingNo)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    


    @staticmethod
    async def searchDirectoryNames(db: AsyncSession, query: str = ""):
        stmt = (
            select(BookFollowUpTable.directoryName)
            .where(BookFollowUpTable.directoryName.isnot(None))
            .where(BookFollowUpTable.directoryName.ilike(f"%{query}%"))
            .distinct()
            .order_by(BookFollowUpTable.directoryName)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    

    #http://127.0.0.1:9000/api/bookFollowUp/getAllDirectoryNames?search=مكتب
    #http://127.0.0.1:9000/api/bookFollowUp/getAllIncomingNo
    #http://127.0.0.1:9000/api/bookFollowUp/getAllBooksNo


  

    
 


    @staticmethod
    async def getAllFilteredBooksNo(
        
        request: Request,
        db: AsyncSession,
        page: int = 1,
        limit: int = 10,
        bookNo: Optional[str] = None,
        bookStatus: Optional[str] = None,
        bookType: Optional[str] = None,
        directoryName: Optional[str] = None,
        incomingNo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve all BookFollowUpTable records with pagination, optional filters, and associated PDFs.
        Returns data for DynamicTable with pdfFiles and username for each record.
        """
        try:
            # Optional filters
            filters = []
            if bookNo:
                filters.append(BookFollowUpTable.bookNo == bookNo.strip())
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())
            if bookType:
                filters.append(BookFollowUpTable.bookType == bookType.strip())
            if directoryName:
                filters.append(BookFollowUpTable.directoryName == directoryName.strip())
            if incomingNo:
                filters.append(BookFollowUpTable.incomingNo == incomingNo.strip())

            # Step 1: Count distinct bookNo
            count_stmt = select(func.count()).select_from(
                select(BookFollowUpTable.bookNo)
                .distinct()
                .filter(*filters)
                .subquery()
            )
            count_result = await db.execute(count_stmt)
            total = count_result.scalar() or 0
            print(f"Total records: {total}, Page: {page}, Limit: {limit}")

            # Step 2: Pagination offset
            offset = (page - 1) * limit

            # Step 3: Select paginated BookFollowUpTable records with username
            book_stmt = (
                select(
                    BookFollowUpTable.id,
                    BookFollowUpTable.bookType,
                    BookFollowUpTable.bookNo,
                    BookFollowUpTable.bookDate,
                    BookFollowUpTable.directoryName,
                    BookFollowUpTable.incomingNo,
                    BookFollowUpTable.incomingDate,
                    BookFollowUpTable.subject,
                    BookFollowUpTable.destination,
                    BookFollowUpTable.bookAction,
                    BookFollowUpTable.bookStatus,
                    BookFollowUpTable.notes,
                    BookFollowUpTable.currentDate,
                    BookFollowUpTable.userID,
                    Users.username
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .filter(*filters)
                .distinct(BookFollowUpTable.bookNo)
                .order_by(BookFollowUpTable.bookNo)
                .offset(offset)
                .limit(limit)
            )
            book_result = await db.execute(book_stmt)
            book_rows = book_result.fetchall()

            # Step 4: Fetch PDFs for all bookNos in the current page, including username
            book_nos = [row.bookNo for row in book_rows]
            pdf_stmt = (
                select(
                    PDFTable.id,
                    PDFTable.bookNo,
                    PDFTable.pdf,
                    PDFTable.currentDate,
                    Users.username
                )
                .outerjoin(Users, PDFTable.userID == Users.id)
                .filter(PDFTable.bookNo.in_(book_nos))
            )
            pdf_result = await db.execute(pdf_stmt)
            pdf_rows = pdf_result.fetchall()

            # Step 5: Group PDFs by bookNo
            pdf_map = {}
            for pdf in pdf_rows:
                if pdf.bookNo not in pdf_map:
                    pdf_map[pdf.bookNo] = []
                pdf_map[pdf.bookNo].append({
                    "id": pdf.id,
                    "pdf": pdf.pdf,
                    "currentDate": pdf.currentDate.strftime('%Y-%m-%d') if pdf.currentDate else None,
                    "username": pdf.username
                })

            # Step 6: Format data
            data = [
                {
                    "id": row.id,
                    "bookType": row.bookType,
                    "bookNo": row.bookNo,
                    "bookDate": row.bookDate.strftime('%Y-%m-%d') if row.bookDate else None,
                    "directoryName": row.directoryName,
                    "incomingNo": row.incomingNo,
                    "incomingDate": row.incomingDate.strftime('%Y-%m-%d') if row.incomingDate else None,
                    "subject": row.subject,
                    "destination": row.destination,
                    "bookAction": row.bookAction,
                    "bookStatus": row.bookStatus.strip().lower() if row.bookStatus else None,
                    "notes": row.notes,
                    "currentDate": row.currentDate.strftime('%Y-%m-%d') if row.currentDate else None,
                    "userID": row.userID,
                    "username": row.username,  # Add username for book creator
                    "pdfFiles": pdf_map.get(row.bookNo, [])  # PDFs with their usernames
                }
                for row in book_rows
            ]
            print(f"Fetched {len(data)} records with PDFs")

            # Step 7: Response
            return {
                "data": data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit
            }
        except Exception as e:
            print(f"Error fetching books: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")     
        




    @staticmethod
    async def update_book(
        db: AsyncSession,
        id: int,
        book_data: BookFollowUpCreate,
        file: Optional[UploadFile] = None,
        user_id: Optional[int] = None
    ) -> int:
        """
        Update a book record by ID with provided fields and optionally add a new PDF.
        Args:
            db: Async SQLAlchemy session.
            id: ID of the book to update.
            book_data: Pydantic model with fields to update (None values ignored).
            file: Optional uploaded PDF file.
            user_id: Optional user ID for PDF record.
        Returns:
            Updated book ID.
        Raises:
            HTTPException: If book not found or database error occurs.
        """
        try:
            # Fetch the existing book
            result = await db.execute(
                select(BookFollowUpTable).filter(BookFollowUpTable.id == id)
            )
            book = result.scalars().first()
            if not book:
                logger.error(f"Book ID {id} not found")
                raise HTTPException(status_code=404, detail="Book not found")

            # Update fields, excluding unset values
            update_data = book_data.model_dump(exclude_unset=True)
            logger.debug(f"Updating book ID {id} with data: {update_data}")
            for key, value in update_data.items():
                if value is not None:  # Skip None values
                    setattr(book, key, value)
            # Set currentDate as string
            book.currentDate = datetime.now().date().strftime('%Y-%m-%d')

            # Handle PDF upload if provided
            if file and user_id:
                count = await PDFService.get_pdf_count(db, id)
                pdf_path = save_pdf_to_server(
                    file.file, book.bookNo, book.bookDate, count, settings.PDF_UPLOAD_PATH
                )
                pdf_data = PDFCreate(
                    bookID=id,
                    bookNo=book.bookNo,
                    countPdf=count,
                    pdf=pdf_path,
                    userID=user_id,
                    currentDate=datetime.now().date().strftime('%Y-%m-%d')
                )
                await PDFService.insert_pdf(db, pdf_data)

                # Attempt to delete scanner file
                try:
                    scanner_path = os.path.join(settings.PDF_SOURCE_PATH, file.filename)
                    os.remove(scanner_path)
                    logger.info(f"Deleted scanner file: {scanner_path}")
                except Exception as e:
                    logger.warning(f"Could not delete scanner file {scanner_path}: {str(e)}")

            # Commit changes
            await db.commit()
            await db.refresh(book)
            logger.info(f"Updated book ID {id}")
            return book.id

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating book ID {id}: {str(e)}")
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
    



    @staticmethod
    async def get_book_with_pdfs(db: AsyncSession, id: int) -> BookFollowUpWithPDFResponseForUpdateByBookID:
        """
        Fetch a book by ID with associated PDFs, PDF count, and username.
        Args:
            db: Async SQLAlchemy session.
            id: Book ID to fetch.
        Returns:
            BookFollowUpWithPDFResponseForUpdateByBookID with book data, PDFs, and username.
        Raises:
            HTTPException: If book not found or database error occurs.
        """
        try:
            # Fetch book, PDFs, and users in a single query
            result = await db.execute(
                select(BookFollowUpTable, PDFTable, Users)
                .outerjoin(PDFTable, BookFollowUpTable.id == PDFTable.bookID)
                .outerjoin(Users, PDFTable.userID == Users.id)  # Join Users with PDFTable.userID
                .filter(BookFollowUpTable.id == id)
            )
            rows = result.fetchall()

            if not rows or not rows[0][0]:
                logger.error(f"Book ID {id} not found")
                raise HTTPException(status_code=404, detail="Book not found")

            # Extract book, PDFs, and user
            book = rows[0][0]
            pdfs = [(row[1], row[2]) for row in rows if row[1]] or []  # Pair PDF with its user

            # Convert date fields to strings for book
            book_date = book.bookDate.strftime('%Y-%m-%d') if isinstance(book.bookDate, date) else book.bookDate
            incoming_date = book.incomingDate.strftime('%Y-%m-%d') if isinstance(book.incomingDate, date) else book.incomingDate
            current_date = book.currentDate.strftime('%Y-%m-%d') if isinstance(book.currentDate, date) else book.currentDate

            # Construct PDF responses
            pdf_responses = [
                PDFResponse(
                    id=pdf.id,
                    bookNo=pdf.bookNo,
                    pdf=pdf.pdf,
                    currentDate=pdf.currentDate,
                    username=user.username if user else None
                )
                for pdf, user in pdfs
            ]

            # Fetch the book owner's username separately if needed
            book_user = None
            if book.userID:
                book_user_result = await db.execute(
                    select(Users).filter(Users.id == book.userID)
                )
                book_user = book_user_result.scalars().first()

            # Construct response
            book_data = BookFollowUpWithPDFResponseForUpdateByBookID(
                id=book.id,
                bookType=book.bookType,
                bookNo=book.bookNo,
                bookDate=book_date,
                directoryName=book.directoryName,
                incomingNo=book.incomingNo,
                incomingDate=incoming_date,
                subject=book.subject,
                destination=book.destination,
                bookAction=book.bookAction,
                bookStatus=book.bookStatus,
                notes=book.notes,
                currentDate=current_date,
                userID=book.userID,
                username=book_user.username if book_user else None,
                countOfPDFs=len(pdf_responses),
                pdfFiles=pdf_responses
            )

            logger.info(f"Fetched book ID {id} with {len(pdf_responses)} PDFs and username {book_data.username}")
            return book_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching book ID {id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")