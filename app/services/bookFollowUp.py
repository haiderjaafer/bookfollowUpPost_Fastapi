import asyncio
from datetime import date, datetime
import os
from typing import Any, Dict, List, Optional
from urllib.parse import unquote
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.helper.save_pdf import async_delayed_delete, save_pdf_to_server
from app.models.PDFTable import PDFCreate, PDFResponse, PDFTable
from app.models.architecture.committees import Committee
from app.models.architecture.department import Department
from app.models.bookFollowUpTable import BookFollowUpResponse, BookFollowUpTable, BookFollowUpCreate, BookFollowUpWithPDFResponseForUpdateByBookID, BookStatusCounts, BookTypeCounts, UserBookCount
from sqlalchemy import select,func,case
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
    


    @staticmethod
    async def getSubjects(db: AsyncSession, query: str = ""):
        stmt = (
            select(BookFollowUpTable.subject)
            .where(BookFollowUpTable.subject.isnot(None))
            .where(BookFollowUpTable.subject.ilike(f"%{query}%"))
            .distinct()
            .order_by(BookFollowUpTable.subject)
        )
        result = await db.execute(stmt)
        return result.scalars().all()
    


    @staticmethod
    async def getDestination(db: AsyncSession, query: str = ""):
        stmt = (
            select(BookFollowUpTable.destination)
            .where(BookFollowUpTable.destination.isnot(None))
            .where(BookFollowUpTable.destination.ilike(f"%{query}%"))
            .distinct()
            .order_by(BookFollowUpTable.destination)
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
        subject: Optional[str] = None,
        incomingNo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve all BookFollowUpTable records with pagination, optional filters, and associated PDFs.
        Includes departmentName and Com without relationships.
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
            if subject:
                filters.append(BookFollowUpTable.subject == subject.strip())
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
            logger.info(f"Total records: {total}, Page: {page}, Limit: {limit}")

            # Step 2: Pagination offset
            offset = (page - 1) * limit

            # Step 3: Select paginated BookFollowUpTable records with username, departmentName, and Com
            book_stmt = (
                select(
                    BookFollowUpTable.id,
                    BookFollowUpTable.bookType,
                    BookFollowUpTable.bookNo,
                    BookFollowUpTable.bookDate,
                    BookFollowUpTable.directoryName,
                    BookFollowUpTable.deID,
                    BookFollowUpTable.incomingNo,
                    BookFollowUpTable.incomingDate,
                    BookFollowUpTable.subject,
                    BookFollowUpTable.destination,
                    BookFollowUpTable.bookAction,
                    BookFollowUpTable.bookStatus,
                    BookFollowUpTable.notes,
                    BookFollowUpTable.currentDate,
                    BookFollowUpTable.userID,
                    Users.username,
                    Department.departmentName,
                    Committee.Com
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(Department, BookFollowUpTable.deID == Department.deID)
                .outerjoin(Committee, Department.coID == Committee.coID)
                .filter(*filters)
                .distinct(BookFollowUpTable.bookNo)
                .order_by(BookFollowUpTable.id)
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
                    "serialNo": offset + i + 1,
                    "id": row.id,
                    "bookType": row.bookType,
                    "bookNo": row.bookNo,
                    "bookDate": row.bookDate.strftime('%Y-%m-%d') if row.bookDate else None,
                    "directoryName": row.directoryName,
                    "incomingNo": row.incomingNo,
                    "incomingDate": row.incomingDate.strftime('%Y-%m-%d') if row.incomingDate else None,
                    "subject": row.subject,
                    # "destination": row.destination,
                    "bookAction": row.bookAction,
                    "bookStatus": row.bookStatus.strip().lower() if row.bookStatus else None,
                    "notes": row.notes,
                    "currentDate": row.currentDate.strftime('%Y-%m-%d') if row.currentDate else None,
                    "userID": row.userID,
                    "username": row.username,
                    "deID": row.deID,
                     "Com": row.Com,
                    "departmentName": row.departmentName,
                   
                    "pdfFiles": pdf_map.get(row.bookNo, [])
                }
                for i, row in enumerate(book_rows)
            ]
            logger.info(f"Fetched {len(data)} records with PDFs")

            # Step 7: Response
            return {
                "data": data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit
            }
        except Exception as e:
            logger.error(f"Error fetching books: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")  

    
 


        



    @staticmethod
    async def update_book(
        db: AsyncSession,
        id: int,
        book_data: BookFollowUpCreate,
        file: Optional[UploadFile] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None
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

            # Handle PDF upload if file is provided
            if file is not None and hasattr(file, 'filename') and file.filename:
                logger.info(f"Processing file upload: {file.filename}")
                
                # Ensure user_id is provided when file is uploaded
                if not user_id:
                    logger.error("User ID is required when uploading a file")
                    raise HTTPException(status_code=400, detail="User ID is required when uploading a file")
                
                try:
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
                    logger.info(f"Successfully saved PDF for book ID {id}")

                    # Delete original file (with delay)
                    scanner_path = os.path.join(settings.PDF_SOURCE_PATH,username, file.filename)
                    print(f"Attempting to delete: {scanner_path}")
                    if os.path.isfile(scanner_path):                                          # os.path.isfile(...) to ensure the file exists
                    # delayed_delete(scanner_path, delay_sec=3)
                        asyncio.create_task(async_delayed_delete(scanner_path, delay_sec=3))   #asyncio.create_task(...) to run async_delayed_delete(...) in the background  and No await, so it doesn’t block the request 

                    else:
                        print(f" File not found for deletion: {scanner_path}")


                        
                except Exception as file_error:
                    logger.error(f"Error processing file upload: {str(file_error)}")
                    raise HTTPException(status_code=500, detail=f"File processing error: {str(file_error)}")
            else:
                logger.info(f"No file provided for book ID {id}, updating only book fields")

            # Commit changes
            await db.commit()
            await db.refresh(book)
            logger.info(f"Successfully updated book ID {id}")
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
                select(BookFollowUpTable, PDFTable, Users, Committee, Department)
                .outerjoin(PDFTable, BookFollowUpTable.id == PDFTable.bookID)
                .outerjoin(Department, BookFollowUpTable.deID == Department.deID)
                .outerjoin(Committee, Department.coID == Committee.coID)
                .outerjoin(Users, PDFTable.userID == Users.id)  # Join Users with PDFTable.userID
                .filter(BookFollowUpTable.id == id)
            )
            rows = result.fetchall()
            
            if not rows or not rows[0][0]:
                logger.error(f"Book ID {id} not found")
                raise HTTPException(status_code=404, detail="Book not found")

            # Extract book, PDFs, user, committee, and department
            book = rows[0][0]
            committee = rows[0][3] if rows[0][3] else None
            department = rows[0][4] if rows[0][4] else None
            
            # Extract coID from the committee object
            coID = committee.coID if committee else None
            
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
                pdfFiles=pdf_responses,
                deID=book.deID,
                coID=coID  # Now using the extracted integer value
            )

            logger.info(f"Fetched book ID {id} with {len(pdf_responses)} PDFs and username {book_data.username}")
            return book_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching book ID {id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")    



    
    @staticmethod
    async def reportBookFollowUp(
        db: AsyncSession,
        bookType: Optional[str] = None,
        bookStatus: Optional[str] = None,
        check: Optional[bool] = False,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns a filtered list of bookFollowUp records based on bookType, bookStatus,
        and date filtering on currentDate. If check is True, filter by date range
        (non-NULL currentDate). If check is False, filter by currentDate IS NULL.

        Args:
            db: AsyncSession for database access
            bookType: Optional filter for book type
            bookStatus: Optional filter for book status
            check: Boolean to enable/disable date range filtering
            startDate: Start date for filtering (YYYY-MM-DD) if check is True
            endDate: End date for filtering (YYYY-MM-DD) if check is True

        Returns:
            List of dictionaries containing book follow-up records
        """
        try:
            # Step 1: Build filters
            filters = []
            if bookType:
                filters.append(BookFollowUpTable.bookType == bookType.strip())
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())

            # Step 2: Add date filter based on check
            if check:
                if not startDate or not endDate:
                    logger.error("startDate and endDate are required when check is True")
                    raise HTTPException(status_code=400, detail="startDate and endDate are required when check is True")
                
                try:
                    start_date = datetime.strptime(startDate, '%Y-%m-%d').date()
                    end_date = datetime.strptime(endDate, '%Y-%m-%d').date()
                    if start_date > end_date:
                        logger.error("startDate cannot be after endDate")
                        raise HTTPException(status_code=400, detail="startDate cannot be after endDate")
                    # Ensure currentDate is not NULL and within range
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                    logger.debug(f"Applying date range filter: {start_date} to {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid date format for startDate or endDate: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            else:
                # When check=False, filter for currentDate IS NULL
                filters.append(BookFollowUpTable.currentDate.is_(None))
                logger.debug("Applying currentDate IS NULL filter")

            # Step 3: Fetch matching records with optional user info
            stmt = (
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
                    Users.username,
                    BookFollowUpTable.deID,
                    Department.departmentName,
                    Committee.Com
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(Department, BookFollowUpTable.deID == Department.deID)
                .outerjoin(Committee, Department.coID == Committee.coID)
                .filter(*filters)
                .order_by(BookFollowUpTable.bookNo)
            )

            result = await db.execute(stmt)
            rows = result.fetchall()

            # Step 4: Format response
            return [
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
                    "bookStatus": row.bookStatus,
                    "notes": row.notes,
                    "currentDate": row.currentDate.strftime('%Y-%m-%d') if row.currentDate else None,
                    "userID": row.userID,
                    "username": row.username,
                    "deID": row.deID,
                    "Com": row.Com,
                    "departmentName": row.departmentName,
                }
                for row in rows
            ]

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reportBookFollowUp: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving filtered report.")



#This means: if BookFollowUpTable.bookType equals 'خارجي', then return 1 (indicating a match). If not, it returns None by default
    @staticmethod
    async def get_book_type_counts(db: AsyncSession) -> BookTypeCounts:
        try:
            query = select(
                func.count(case((BookFollowUpTable.bookType == 'خارجي', 1))).label('External'),  #label is a way to assign a name to a column in the result set
                func.count(case((BookFollowUpTable.bookType == 'داخلي', 1))).label('Internal'),  #case returns 1 if the condition is met (the bookType matches)
                func.count(case((BookFollowUpTable.bookType == 'فاكس', 1))).label('Fax')         
            )
            result = await db.execute(query)
            row:BookTypeCounts = result.first()
            print(f"row get_book_type_counts {row}")
            return BookTypeCounts(
                External=row.External or 0, 
                Internal=row.Internal or 0,
                Fax=row.Fax or 0
            )
        except Exception as e:
            print(f"Error in get_book_type_counts: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving filtered BookTypeCounts")
        


    @staticmethod
    async def get_book_status_counts(db: AsyncSession) -> BookStatusCounts:
        try:
            query = select(
                func.count(case((BookFollowUpTable.bookStatus == 'منجز', 1))).label('Accomplished'),
                func.count(case((BookFollowUpTable.bookStatus == 'قيد الانجاز', 1))).label('Pending'),
                func.count(case((BookFollowUpTable.bookStatus == 'مداولة', 1))).label('Deliberation')
            )
            result = await db.execute(query)
            row = result.first()
            return BookStatusCounts(
                Accomplished=row.Accomplished or 0,
                Pending=row.Pending or 0,
                Deliberation=row.Deliberation or 0
            )
        except Exception as e:
            print(f"Error in get_book_status_counts: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving filtered BookStatusCounts")



    @staticmethod
    async def get_user_book_counts(db: AsyncSession) -> List[UserBookCount]:
        try:
            query = (
                select(Users.username, func.count(BookFollowUpTable.id).label('bookCount'))
                .join(Users, BookFollowUpTable.userID == Users.id)
                .group_by(Users.username)
                .order_by(func.count(BookFollowUpTable.id).desc())
            )
            result = await db.execute(query)
            rows:UserBookCount = result.fetchall()
            return [UserBookCount(username=row.username, bookCount=row.bookCount) for row in rows]
        except Exception as e:
            print(f"Error in get_user_book_counts: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving filtered UserBookCount.")   



 
    @staticmethod
    async def getRecordBySubject(
        db: AsyncSession,
        subject: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Step 1: Validate input
            if not subject:
                logger.warning("No subject provided in query")
                raise HTTPException(
                    status_code=400,
                    detail="Subject query parameter is required"
                )

            # Decode URL-encoded subject
            decoded_subject = unquote(subject).strip()
            logger.info(f"Decoded subject: {decoded_subject}")

            # Additional validation
            if len(decoded_subject) < 1:
                logger.error("Subject is empty after decoding")
                raise HTTPException(
                    status_code=400,
                    detail="Subject cannot be empty"
                )
            if len(decoded_subject) > 255:  # Adjust based on your schema
                logger.error(f"Subject too long: {len(decoded_subject)} characters")
                raise HTTPException(
                    status_code=400,
                    detail="Subject exceeds maximum length of 255 characters"
                )
            if any(char in decoded_subject for char in [';', '--', '/*', '*/']):
                logger.error(f"Invalid characters in subject: {decoded_subject}")
                raise HTTPException(
                    status_code=400,
                    detail="Subject contains invalid characters"
                )

            # Step 2: Query for the first matching record with user and PDF count
            # Use a subquery for countOfPDFs to avoid GROUP BY issues
            pdf_count_subquery = (
                select(func.count(PDFTable.id).label("countOfPDFs"))
                .where(PDFTable.bookID == BookFollowUpTable.id)
                .correlate(BookFollowUpTable)
                .scalar_subquery()
            )

            stmt = (
                select(
                    BookFollowUpTable,
                    Users.username,
                    pdf_count_subquery.label("countOfPDFs")
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .where(BookFollowUpTable.subject == decoded_subject)
                .limit(1)  # SQL Server: TOP 1
            )
            logger.debug(f"Executing query: {stmt}")
            result = await db.execute(stmt)
            record = result.first()

            if record is None:
                logger.info(f"No record found for subject: {decoded_subject}")
                raise HTTPException(
                    status_code=404,
                    detail=f"No record found for subject: {decoded_subject}"
                )

            book_followup, username, count_of_pdfs = record

            # Step 3: Fetch associated PDFs
            pdf_stmt = (
                select(PDFTable)
                .where(PDFTable.bookID == book_followup.id)
            )
            pdf_result = await db.execute(pdf_stmt)
            pdfs = pdf_result.scalars().all()

            # Step 4: Format response
            response = BookFollowUpWithPDFResponseForUpdateByBookID(
                id=book_followup.id,
                bookType=book_followup.bookType,
                bookNo=book_followup.bookNo,
                bookDate=book_followup.bookDate.strftime("%Y-%m-%d") if book_followup.bookDate else None,
                directoryName=book_followup.directoryName,
                # coID=book_followup.coID,
                deID=book_followup.deID,
                incomingNo=book_followup.incomingNo,
                incomingDate=book_followup.incomingDate.strftime("%Y-%m-%d") if book_followup.incomingDate else None,
                subject=book_followup.subject,
                destination=book_followup.destination,
                bookAction=book_followup.bookAction,
                bookStatus=book_followup.bookStatus,
                notes=book_followup.notes,
                currentDate=book_followup.currentDate.strftime("%Y-%m-%d") if book_followup.currentDate else None,
                userID=book_followup.userID,
                username=username,
                countOfPDFs=count_of_pdfs,
                pdfFiles=[
                    PDFResponse(
                        id=pdf.id,
                        bookNo=pdf.bookNo,
                        pdf=pdf.pdf,
                        currentDate=pdf.currentDate.strftime("%Y-%m-%d") if pdf.currentDate else None,
                        username=username
                    )
                    for pdf in pdfs
                ]
            )

            logger.info(f"Found record with ID: {book_followup.id} for subject: {decoded_subject}")
            return {
                "data":response
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in getRecordBySubject: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="Internal server error while fetching record"
            )