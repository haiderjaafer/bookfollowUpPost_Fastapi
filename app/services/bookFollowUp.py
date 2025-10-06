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
from app.models.bookFollowUpTable import BookFollowUpResponse, BookFollowUpTable, BookFollowUpCreate, BookFollowUpWithPDFResponseForUpdateByBookID, BookJunctionBridge, BookStatusCounts, BookTypeCounts, CommitteeDepartmentsJunction, UserBookCount
from sqlalchemy import String, and_, cast, delete, select,func,case, text,desc
from fastapi import HTTPException, Request, UploadFile
from app.models.users import Users
from app.services.pdf_service import PDFService
from app.database.config import settings
from difflib import SequenceMatcher
from sqlalchemy import or_, func
import logging
from sqlalchemy.exc import IntegrityError

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:  # Avoid duplicate handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )



class BookFollowUpService:
    
    @staticmethod
    async def get_or_create_junction(db: AsyncSession, coID: int, deID: int) -> int:
        """
        Get existing junction or create new one for committee-department pair
        Optimized for SQL Server with proper error handling
        """
        
        
        try:
            # Try to find existing junction first
            stmt = select(CommitteeDepartmentsJunction).where(
                CommitteeDepartmentsJunction.coID == coID,
                CommitteeDepartmentsJunction.deID == deID
            )
            result = await db.execute(stmt)
            junction = result.scalars().first()
            
            if junction:
                print(f"Found existing junction: {junction.id} for coID={coID}, deID={deID}")
                return junction.id
            
            # Create new junction if doesn't exist
            new_junction = CommitteeDepartmentsJunction(
                coID=coID,
                deID=deID
            )
            db.add(new_junction)
            await db.flush()  # Flush to get ID without full commit
            junction_id = new_junction.id
            print(f"Created new junction: {junction_id} for coID={coID}, deID={deID}")
            return junction_id
            
        except IntegrityError as e:
            # Handle unique constraint violation (race condition)
            await db.rollback()
            print(f"IntegrityError for coID={coID}, deID={deID}: {str(e)}")
            
            # Re-fetch the existing record
            stmt = select(CommitteeDepartmentsJunction).where(
                CommitteeDepartmentsJunction.coID == coID,
                CommitteeDepartmentsJunction.deID == deID
            )
            result = await db.execute(stmt)
            junction = result.scalars().first()
            
            if junction:
                print(f"Retrieved existing junction after conflict: {junction.id}")
                return junction.id
            else:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create or retrieve junction for coID={coID}, deID={deID}"
                )
    
    @staticmethod
    async def insert_book(db: AsyncSession, book: BookFollowUpCreate) -> int:
        """
        Insert new book record with SQL Server optimized date handling.
        Handles optional incomingNo and incomingDate for SECRET book types.
        """
        book_dict = book.model_dump(exclude_none=True)
        
        # Handle date conversion for SQL Server
        for date_field in ['bookDate', 'incomingDate', 'currentDate']:
            if date_field in book_dict and book_dict[date_field]:
                if isinstance(book_dict[date_field], str):
                    try:
                        book_dict[date_field] = datetime.strptime(
                            book_dict[date_field], '%Y-%m-%d'
                        ).date()
                    except ValueError as e:
                        print(f"Invalid date format for {date_field}: {book_dict[date_field]}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid date format for {date_field}. Use YYYY-MM-DD"
                        )
        
        # For SECRET books, ensure both incomingNo and incomingDate are None
        if book_dict.get('bookType') == 'سري':
            book_dict['incomingNo'] = None
            book_dict['incomingDate'] = None
            print("Removed incomingNo and incomingDate for SECRET book type")
        
        new_book = BookFollowUpTable(**book_dict)
        db.add(new_book)
        await db.flush()
        book_id = new_book.id
        print(f"Created book record with ID: {book_id} (Type: {book_dict.get('bookType')})")
        return book_id
  

    
    @staticmethod
    async def create_book_junction_bridge(db: AsyncSession, book_id: int, junction_id: int) -> int:
        """
        Create bridge record for many-to-many relationship
        Handles SQL Server specific constraints
        """
        
        try:
            # Check if bridge already exists (prevent duplicates)
            existing_stmt = select(BookJunctionBridge).where(
                BookJunctionBridge.bookID == book_id,
                BookJunctionBridge.junctionID == junction_id
            )
            result = await db.execute(existing_stmt)
            existing_bridge = result.scalars().first()
            
            if existing_bridge:
                print(f"Bridge already exists: {existing_bridge.id} for bookID={book_id}, junctionID={junction_id}")
                return existing_bridge.id
            
            # Create new bridge record
            bridge = BookJunctionBridge(
                bookID=book_id,
                junctionID=junction_id
            )
            db.add(bridge)
            await db.flush()  # Get ID without full commit
            bridge_id = bridge.id
            print(f"Created bridge record: {bridge_id} for bookID={book_id}, junctionID={junction_id}")
            return bridge_id
            
        except IntegrityError as e:
            await db.rollback()
            print(f"IntegrityError creating bridge for bookID={book_id}, junctionID={junction_id}: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to create bridge record for book {book_id} and junction {junction_id}"
            )
    
    @staticmethod

    
    @staticmethod
    async def create_book_junction_bridge(db: AsyncSession, book_id: int, junction_id: int) -> int:
        """
        Create bridge record for many-to-many relationship
        Handles SQL Server specific constraints
        """
        
        try:
            # Check if bridge already exists (prevent duplicates)
            existing_stmt = select(BookJunctionBridge).where(
                BookJunctionBridge.bookID == book_id,
                BookJunctionBridge.junctionID == junction_id
            )
            result = await db.execute(existing_stmt)
            existing_bridge = result.scalars().first()
            
            if existing_bridge:
                print(f"Bridge already exists: {existing_bridge.id} for bookID={book_id}, junctionID={junction_id}")
                return existing_bridge.id
            
            # Create new bridge record
            bridge = BookJunctionBridge(
                bookID=book_id,
                junctionID=junction_id
            )
            db.add(bridge)
            await db.flush()  # Get ID without full commit
            bridge_id = bridge.id
            print(f"Created bridge record: {bridge_id} for bookID={book_id}, junctionID={junction_id}")
            return bridge_id
            
        except IntegrityError as e:
            await db.rollback()
            print(f"IntegrityError creating bridge for bookID={book_id}, junctionID={junction_id}: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to create bridge record for book {book_id} and junction {junction_id}"
            )
    
    @staticmethod

    async def get_book_with_all_departments(db: AsyncSession, book_id: int):
        """
        Get book with ALL associated departments through bridge records
        SQL Server optimized query with proper joins
        """
        
        # Raw SQL for complex query with multiple joins (SQL Server optimized)
        query = text("""
            SELECT 
                b.id as book_id,
                b.bookNo,
                b.bookType,
                b.subject,
                b.bookStatus,
                c.coID,
                c.Com as committee_name,
                d.deID,
                d.departmentName,
                j.id as junction_id,
                br.id as bridge_id
            FROM bookFollowUpTable b
            INNER JOIN book_junction_bridge br ON b.id = br.bookID
            INNER JOIN committee_departments_junction j ON br.junctionID = j.id
            INNER JOIN committees c ON j.coID = c.coID
            INNER JOIN departments d ON j.deID = d.deID
            WHERE b.id = :book_id
            ORDER BY d.departmentName
        """)
        
        result = await db.execute(query, {"book_id": book_id})
        rows = result.fetchall()
        
        return rows




    
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
        Updated for new multi-department schema with junctions and bridges.
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

            # Step 3: Complex query to get book with ALL associated departments
            # Using CTE to get books with their primary junction info, then collect all departments
            book_with_primary_junction = (
                select(
                    BookFollowUpTable.id,
                    BookFollowUpTable.bookType,
                    BookFollowUpTable.bookNo,
                    BookFollowUpTable.bookDate,
                    BookFollowUpTable.directoryName,
                    BookFollowUpTable.junctionID,
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
                    # Get primary committee and department from junctionID
                    Committee.coID,
                    Committee.Com,
                    Department.deID.label('primary_deID'),
                    Department.departmentName.label('primary_departmentName')
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(
                    CommitteeDepartmentsJunction, 
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .outerjoin(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                .outerjoin(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                .filter(*filters)
                .distinct(BookFollowUpTable.bookNo)
                .order_by(BookFollowUpTable.currentDate.desc())
                .offset(offset)
                .limit(limit)
            )
            
            book_result = await db.execute(book_with_primary_junction)
            book_rows = book_result.fetchall()

            # Step 4: Get ALL departments for each book through bridge records
            book_ids = [row.id for row in book_rows]
            if book_ids:
                # Query to get all departments for each book
                all_departments_stmt = (
                    select(
                        BookFollowUpTable.id.label('book_id'),
                        BookFollowUpTable.bookNo,
                        Department.deID,
                        Department.departmentName,
                        Committee.coID,
                        Committee.Com
                    )
                    .select_from(BookFollowUpTable)
                    .join(BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID)
                    .join(CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id)
                    .join(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                    .join(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                    .filter(BookFollowUpTable.id.in_(book_ids))
                    .order_by(BookFollowUpTable.id, Department.departmentName)
                )
                
                dept_result = await db.execute(all_departments_stmt)
                dept_rows = dept_result.fetchall()
                
                # Group departments by book_id
                dept_map = {}
                for dept in dept_rows:
                    if dept.book_id not in dept_map:
                        dept_map[dept.book_id] = []
                    dept_map[dept.book_id].append({
                        "deID": dept.deID,
                        "departmentName": dept.departmentName,
                        "coID": dept.coID,
                        "Com": dept.Com
                    })
            else:
                dept_map = {}

            # Step 5: Fetch PDFs for all bookNos in the current page
            book_nos = [row.bookNo for row in book_rows]
            if book_nos:
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

                # Group PDFs by bookNo
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
            else:
                pdf_map = {}

            # Step 6: Format data with multiple departments
            data = []
            for i, row in enumerate(book_rows):
                book_departments = dept_map.get(row.id, [])
                
                # Create department summary strings
                dept_names = [dept["departmentName"] for dept in book_departments if dept["departmentName"]]
                dept_ids = [dept["deID"] for dept in book_departments]
                
                data.append({
                    "serialNo": offset + i + 1,
                    "id": row.id,
                    "bookType": row.bookType,
                    "bookNo": row.bookNo,
                    "bookDate": row.bookDate.strftime('%Y-%m-%d') if row.bookDate else None,
                    "directoryName": row.directoryName,
                    "incomingNo": row.incomingNo,
                    "incomingDate": row.incomingDate.strftime('%Y-%m-%d') if row.incomingDate else None,
                    "subject": row.subject,
                    "bookAction": row.bookAction,
                    "bookStatus": row.bookStatus.strip().lower() if row.bookStatus else None,
                    "notes": row.notes,
                    "currentDate": row.currentDate.strftime('%Y-%m-%d') if row.currentDate else None,
                    "userID": row.userID,
                    "username": row.username,
                    
                    # Primary junction info (for backward compatibility)
                    "deID": row.primary_deID,
                    "departmentName": row.primary_departmentName,
                    "coID": row.coID,
                    "Com": row.Com,
                    
                    # All departments for this book
                    "all_departments": book_departments,
                    "department_names": ", ".join(dept_names),  # Comma-separated string
                    "department_count": len(book_departments),
                    
                    "pdfFiles": pdf_map.get(row.bookNo, [])
                })

            logger.info(f"Fetched {len(data)} records with PDFs and departments")

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
    async def update_book_with_multi_departments(
        db: AsyncSession,
        id: int,
        book_data: BookFollowUpCreate,
        committee_id: Optional[int] = None,
        department_ids: Optional[List[int]] = None,
        file: Optional[UploadFile] = None,
        user_id: Optional[int] = None,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a book record with multi-department support and optionally add a new PDF.
        
        Args:
            db: Async SQLAlchemy session.
            id: ID of the book to update.
            book_data: Pydantic model with fields to update (None values ignored).
            committee_id: Committee ID for junction management.
            department_ids: List of department IDs for multi-department assignment.
            file: Optional uploaded PDF file.
            user_id: Optional user ID for PDF record.
            username: Username for file path management.
            
        Returns:
            Dictionary with update results including book_id, junction_ids, etc.
            
        Raises:
            HTTPException: If book not found or database error occurs.
        """
        try:
            # Step 1: Fetch the existing book
            result = await db.execute(
                select(BookFollowUpTable).filter(BookFollowUpTable.id == id)
            )
            book = result.scalars().first()
            if not book:
                logger.error(f"Book ID {id} not found")
                raise HTTPException(status_code=404, detail="Book not found")

            logger.info(f"Updating book ID {id} with multi-department support")

            # Step 2: Handle multi-department junction updates if provided
            junction_ids = []
            bridge_ids = []
            
            if committee_id and department_ids:
                logger.info(f"Updating multi-department assignment: Committee {committee_id} with departments {department_ids}")
                
                # Create/get junctions for each committee-department pair
                for dept_id in department_ids:
                    junction_id = await BookFollowUpService.get_or_create_junction(db, committee_id, dept_id)
                    junction_ids.append(junction_id)
                    logger.info(f"Junction ID for Committee {committee_id} + Department {dept_id}: {junction_id}")

                # Update book's primary junction to the first one
                if junction_ids:
                    book.junctionID = junction_ids[0]
                    logger.info(f"Set primary junctionID to {junction_ids[0]}")

                # Clear existing bridge records for this book
                await db.execute(
                    delete(BookJunctionBridge).where(BookJunctionBridge.bookID == id)
                )
                logger.info(f"Cleared existing bridge records for book {id}")

                # Create new bridge records for all junctions
                for junction_id in junction_ids:
                    bridge_id = await BookFollowUpService.create_book_junction_bridge(db, id, junction_id)
                    bridge_ids.append(bridge_id)
                    logger.info(f"Created bridge record {bridge_id} for book {id} and junction {junction_id}")

            # Step 3: Update book fields, excluding unset values
            update_data = book_data.model_dump(exclude_unset=True)
            logger.debug(f"Updating book ID {id} with data: {update_data}")
            
            for key, value in update_data.items():
                if value is not None and hasattr(book, key):  # Skip None values and ensure field exists
                    # Handle date conversion if needed
                    if key in ['bookDate', 'incomingDate'] and isinstance(value, str):
                        try:
                            # Validate date format
                            datetime.strptime(value, '%Y-%m-%d')
                            setattr(book, key, value)
                        except ValueError:
                            logger.warning(f"Invalid date format for {key}: {value}")
                            continue
                    else:
                        setattr(book, key, value)
            
            # Update currentDate
            # book.currentDate = datetime.now().date()

            # Step 4: Handle PDF upload if file is provided
            pdf_added = False
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
                        currentDate=datetime.now().date().isoformat()
                    )
                    await PDFService.insert_pdf(db, pdf_data)
                    logger.info(f"Successfully saved PDF for book ID {id}")
                    pdf_added = True

                    # Delete original file (with delay) if username is provided
                    if username:
                        scanner_path = os.path.join(settings.PDF_SOURCE_PATH, username, file.filename)
                        logger.info(f"Attempting to delete: {scanner_path}")
                        if os.path.isfile(scanner_path):
                            asyncio.create_task(async_delayed_delete(scanner_path, delay_sec=3))
                        else:
                            logger.warning(f"File not found for deletion: {scanner_path}")
                            
                except Exception as file_error:
                    logger.error(f"Error processing file upload: {str(file_error)}")
                    raise HTTPException(status_code=500, detail=f"File processing error: {str(file_error)}")
            else:
                logger.info(f"No file provided for book ID {id}, updating only book fields")

            # Step 5: Commit all changes
            await db.commit()
            await db.refresh(book)
            logger.info(f"Successfully updated book ID {id} with {len(junction_ids)} junctions and {len(bridge_ids)} bridges")

            # Step 6: Return comprehensive result
            return {
                "book_id": book.id,
                "committee_id": committee_id,
                "department_ids": department_ids,
                "junction_ids": junction_ids,
                "bridge_ids": bridge_ids,
                "pdf_added": pdf_added,
                "total_departments": len(department_ids) if department_ids else 0
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating book ID {id}: {str(e)}")
            await db.rollback()
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
            # book.currentDate = datetime.now().date().strftime('%Y-%m-%d')

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
        Fetch a book by ID with associated PDFs, PDF count, username, and all associated departments.
        Updated for new multi-department schema with junctions and bridges.
        Args:
            db: Async SQLAlchemy session.
            id: Book ID to fetch.
        Returns:
            BookFollowUpWithPDFResponseForUpdateByBookID with book data, PDFs, and all departments.
        Raises:
            HTTPException: If book not found or database error occurs.
        """
        try:
            # Step 1: Fetch main book data with primary junction info
            book_query = select(
                BookFollowUpTable,
                Committee.coID,
                Committee.Com,
                Department.deID,
                Department.departmentName,
                Users.username.label('book_username')
            ).outerjoin(
                CommitteeDepartmentsJunction, 
                BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
            ).outerjoin(
                Committee, CommitteeDepartmentsJunction.coID == Committee.coID
            ).outerjoin(
                Department, CommitteeDepartmentsJunction.deID == Department.deID
            ).outerjoin(
                Users, BookFollowUpTable.userID == Users.id
            ).filter(BookFollowUpTable.id == id)

            result = await db.execute(book_query)
            book_row = result.first()
            
            if not book_row or not book_row[0]:
                logger.error(f"Book ID {id} not found")
                raise HTTPException(status_code=404, detail="Book not found")

            book = book_row[0]
            primary_committee = book_row[1]  # coID
            primary_committee_name = book_row[2]  # Com
            primary_department = book_row[3]  # deID
            primary_department_name = book_row[4]  # departmentName
            book_username = book_row[5]

            # Step 2: Get ALL departments for this book through bridge records
            all_departments_query = select(
                Department.deID,
                Department.departmentName,
                Committee.coID,
                Committee.Com
            ).select_from(BookFollowUpTable).join(
                BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID
            ).join(
                CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id
            ).join(
                Committee, CommitteeDepartmentsJunction.coID == Committee.coID
            ).join(
                Department, CommitteeDepartmentsJunction.deID == Department.deID
            ).filter(BookFollowUpTable.id == id).order_by(Department.departmentName)

            dept_result = await db.execute(all_departments_query)
            dept_rows = dept_result.fetchall()

            # Process all departments
            all_departments = []
            for dept_row in dept_rows:
                all_departments.append({
                    "deID": dept_row[0],
                    "departmentName": dept_row[1],
                    "coID": dept_row[2],
                    "Com": dept_row[3]
                })

            # Create department summary
            dept_names = [dept["departmentName"] for dept in all_departments if dept["departmentName"]]
            department_names = ", ".join(dept_names) if dept_names else None

            # Step 3: Fetch PDFs associated with this book
            pdf_query = select(
                PDFTable,
                Users.username.label('pdf_username')
            ).outerjoin(
                Users, PDFTable.userID == Users.id
            ).filter(PDFTable.bookID == id)

            pdf_result = await db.execute(pdf_query)
            pdf_rows = pdf_result.fetchall()

            # Construct PDF responses
            pdf_responses = []
            for pdf_row in pdf_rows:
                pdf = pdf_row[0]
                pdf_username = pdf_row[1]
                pdf_responses.append(PDFResponse(
                    id=pdf.id,
                    bookNo=pdf.bookNo,
                    pdf=pdf.pdf,
                    currentDate=pdf.currentDate.strftime('%Y-%m-%d') if pdf.currentDate else None,
                    username=pdf_username
                ))

            # Step 4: Convert date fields to strings for book
            book_date = book.bookDate.strftime('%Y-%m-%d') if isinstance(book.bookDate, date) else book.bookDate
            incoming_date = book.incomingDate.strftime('%Y-%m-%d') if isinstance(book.incomingDate, date) else book.incomingDate
            current_date = book.currentDate.strftime('%Y-%m-%d') if isinstance(book.currentDate, date) else book.currentDate

            # Step 5: Construct response with multi-department support
            book_data = BookFollowUpWithPDFResponseForUpdateByBookID(
                id=book.id,
                bookType=book.bookType,
                bookNo=book.bookNo,
                bookDate=book_date,
                directoryName=book.directoryName,
                junctionID=book.junctionID,
                
                # Primary department/committee info
                coID=primary_committee,
                deID=primary_department,
                Com=primary_committee_name,
                departmentName=primary_department_name,
                
                # Multi-department info
                all_departments=all_departments,
                department_names=department_names,
                department_count=len(all_departments),
                
                incomingNo=book.incomingNo,
                incomingDate=incoming_date,
                subject=book.subject,
                destination=book.destination,
                bookAction=book.bookAction,
                bookStatus=book.bookStatus,
                notes=book.notes,
                currentDate=current_date,
                userID=book.userID,
                username=book_username,
                countOfPDFs=len(pdf_responses),
                pdfFiles=pdf_responses
            )

            logger.info(f"Fetched book ID {id} with {len(pdf_responses)} PDFs, {len(all_departments)} departments, and username {book_data.username}")
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
        Returns a filtered list of bookFollowUp records with multi-department support.
        Single committee with multiple departments per book.
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
                    
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                    logger.debug(f"Applying date range filter: {start_date} to {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid date format for startDate or endDate: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            else:
                filters.append(BookFollowUpTable.currentDate.is_(None))
                logger.debug("Applying currentDate IS NULL filter")

            # Step 3: Fetch matching records with primary junction info
            stmt = (
                select(
                    BookFollowUpTable.id,
                    BookFollowUpTable.bookType,
                    BookFollowUpTable.bookNo,
                    BookFollowUpTable.bookDate,
                    BookFollowUpTable.directoryName,
                    BookFollowUpTable.junctionID,
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
                    # Primary committee and department from junction
                    Committee.coID,
                    Committee.Com,
                    Department.deID,
                    Department.departmentName
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(
                    CommitteeDepartmentsJunction,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .outerjoin(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                .outerjoin(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                .filter(*filters)
                .order_by(BookFollowUpTable.bookNo)
            )

            result = await db.execute(stmt)
            rows = result.fetchall()

            # Step 4: Get book IDs for multi-department queries
            book_ids = [row.id for row in rows]
            
            # Step 5: Get all departments for each book (single committee, multiple departments)
            dept_map = {}
            if book_ids:
                dept_query = select(
                    BookFollowUpTable.id.label('book_id'),
                    Department.deID,
                    Department.departmentName,
                    Committee.coID,
                    Committee.Com
                ).select_from(BookFollowUpTable).join(
                    BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID
                ).join(
                    CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id
                ).join(
                    Committee, CommitteeDepartmentsJunction.coID == Committee.coID
                ).join(
                    Department, CommitteeDepartmentsJunction.deID == Department.deID
                ).filter(BookFollowUpTable.id.in_(book_ids))
                
                dept_result = await db.execute(dept_query)
                dept_rows = dept_result.fetchall()
                
                for dept_row in dept_rows:
                    book_id = dept_row.book_id
                    if book_id not in dept_map:
                        dept_map[book_id] = []
                    dept_map[book_id].append({
                        "deID": dept_row.deID,
                        "departmentName": dept_row.departmentName,
                        "coID": dept_row.coID,
                        "Com": dept_row.Com
                    })

            # Step 6: Format response with multi-department info (REMOVED multi-committee)
            response = []
            for idx, row in enumerate(rows):
                all_departments = dept_map.get(row.id, [])
                
                # Create department summary
                dept_names = [dept["departmentName"] for dept in all_departments if dept["departmentName"]]
                department_names = ", ".join(dept_names) if dept_names else row.departmentName
                
                response.append({
                    "serialNo": idx + 1,
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
                    
                    # Single committee info
                    "coID": row.coID,
                    "Com": row.Com,
                    "deID": str(row.deID) if row.deID else None,
                    "departmentName": row.departmentName,
                    
                    # Multi-department info (for single committee)
                    "all_departments": all_departments,
                    "department_names": department_names,
                    "department_count": len(all_departments),
                    
                    "len": len(rows)
                })

            logger.info(f"Report generated: {len(response)} records")
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reportBookFollowUp: {str(e)}", exc_info=True)
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
            if not subject:
                raise HTTPException(status_code=400, detail="Subject is required")

            decoded_subject = unquote(subject).strip()
            logger.info(f"Searching for subject: {decoded_subject}")

            # Step 1: Try exact match first with multi-department support
            pdf_count_subquery = (
                select(func.count(PDFTable.id))
                .where(PDFTable.bookID == BookFollowUpTable.id)
                .scalar_subquery()
            )

            # Main query with junction support
            base_query = (
                select(
                    BookFollowUpTable,
                    Users.username,
                    pdf_count_subquery.label("countOfPDFs"),
                    Committee.coID,
                    Committee.Com,
                    Department.deID,
                    Department.departmentName
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(
                    CommitteeDepartmentsJunction,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .outerjoin(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                .outerjoin(Department, CommitteeDepartmentsJunction.deID == Department.deID)
            )

            # Exact match query
            exact_stmt = base_query.where(BookFollowUpTable.subject == decoded_subject)
            result = await db.execute(exact_stmt)
            records = result.all()
            
            # Step 2: If no exact match, try fuzzy matching
            if not records:
                logger.info(f"No exact match found, trying fuzzy search for: {decoded_subject}")
                
                # Get all subjects for fuzzy matching
                all_subjects_stmt = select(BookFollowUpTable.subject).distinct()
                all_subjects_result = await db.execute(all_subjects_stmt)
                all_subjects = [row[0] for row in all_subjects_result.all() if row[0]]
                
                # Find best matches using fuzzy matching
                best_matches = []
                for db_subject in all_subjects:
                    similarity = SequenceMatcher(None, decoded_subject.lower(), db_subject.lower()).ratio()
                    if similarity > 0.8:  # 80% similarity threshold
                        best_matches.append((db_subject, similarity))
                
                # Sort by similarity and get the best match
                if best_matches:
                    best_matches.sort(key=lambda x: x[1], reverse=True)
                    best_subject = best_matches[0][0]
                    logger.info(f"Found fuzzy match: '{best_subject}' with similarity: {best_matches[0][1]:.2f}")
                    
                    # Query with the best matching subject
                    fuzzy_stmt = base_query.where(BookFollowUpTable.subject == best_subject)
                    result = await db.execute(fuzzy_stmt)
                    records = result.all()

            # Step 3: If still no match, try partial matching
            if not records:
                logger.info(f"No fuzzy match found, trying partial search")
                
                # Extract key words (remove common Arabic words)
                common_words = ['من', 'في', 'على', 'إلى', 'عن', 'مع', 'لل', 'ال', 'و', 'أو']
                search_words = [word for word in decoded_subject.split() if len(word) > 2 and word not in common_words]
                
                if search_words:
                    # Create LIKE conditions for each significant word
                    conditions = []
                    for word in search_words[:5]:  # Limit to first 5 significant words
                        conditions.append(BookFollowUpTable.subject.ilike(f'%{word}%'))
                    
                    partial_stmt = base_query.where(or_(*conditions))
                    result = await db.execute(partial_stmt)
                    records = result.all()

            if not records:
                # Log available subjects for debugging
                debug_stmt = select(BookFollowUpTable.subject).limit(10)
                debug_result = await db.execute(debug_stmt)
                available_subjects = [row[0] for row in debug_result.all()]
                logger.info(f"Available subjects (first 10): {available_subjects}")
                
                raise HTTPException(
                    status_code=404, 
                    detail=f"No record found for subject: {decoded_subject[:100]}..."
                )

            # Step 4: Process records and get all departments for each book
            response_array = []
            for record in records:
                book_followup = record[0]
                username = record[1]
                count_of_pdfs = record[2]
                primary_committee_id = record[3]  # coID
                primary_committee_name = record[4]  # Com
                primary_department_id = record[5]  # deID
                primary_department_name = record[6]  # departmentName

                # Get ALL departments for this book through bridge records
                all_departments_query = select(
                    Department.deID,
                    Department.departmentName,
                    Committee.coID,
                    Committee.Com
                ).select_from(BookFollowUpTable).join(
                    BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID
                ).join(
                    CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id
                ).join(
                    Committee, CommitteeDepartmentsJunction.coID == Committee.coID
                ).join(
                    Department, CommitteeDepartmentsJunction.deID == Department.deID
                ).filter(BookFollowUpTable.id == book_followup.id).order_by(Department.departmentName)

                dept_result = await db.execute(all_departments_query)
                dept_rows = dept_result.fetchall()

                # Process all departments
                all_departments = []
                for dept_row in dept_rows:
                    all_departments.append({
                        "deID": dept_row[0],
                        "departmentName": dept_row[1],
                        "coID": dept_row[2],
                        "Com": dept_row[3]
                    })

                # Create department summary
                dept_names = [dept["departmentName"] for dept in all_departments if dept["departmentName"]]
                department_names = ", ".join(dept_names) if dept_names else None

                # Get PDFs for this book
                pdf_stmt = select(PDFTable).where(PDFTable.bookID == book_followup.id)
                pdf_result = await db.execute(pdf_stmt)
                pdfs = pdf_result.scalars().all()

                # Build response with multi-department support
                response = BookFollowUpWithPDFResponseForUpdateByBookID(
                    id=book_followup.id,
                    bookType=book_followup.bookType,
                    bookNo=book_followup.bookNo,
                    bookDate=book_followup.bookDate.strftime("%Y-%m-%d") if book_followup.bookDate else None,
                    directoryName=book_followup.directoryName,
                    junctionID=book_followup.junctionID,
                    
                    # Primary department/committee info
                    coID=primary_committee_id,
                    deID=primary_department_id,
                    Com=primary_committee_name,
                    departmentName=primary_department_name,
                    
                    # Multi-department info
                    all_departments=all_departments,
                    department_names=department_names,
                    department_count=len(all_departments),
                    
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

                response_array.append(response)

            logger.info(f"Found {len(response_array)} records for subject search")
            return {"data": response_array}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in getRecordBySubject: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")


    
    @staticmethod
    async def reportBookFollowUpWithStats(
        db: AsyncSession,
        bookType: Optional[str] = None,
        bookStatus: Optional[str] = None,
        check: Optional[bool] = False,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns a filtered list of bookFollowUp records with department statistics.
        
        Args:
            db: AsyncSession for database access
            bookType: Optional filter for book type
            bookStatus: Optional filter for book status
            check: Boolean to enable/disable date range filtering
            startDate: Start date for filtering (YYYY-MM-DD) if check is True
            endDate: End date for filtering (YYYY-MM-DD) if check is True

        Returns:
            Dictionary containing records and statistics
        """
        try:
            # Step 1: Build filters (same as original)
            filters = []
            if bookType:
                filters.append(BookFollowUpTable.bookType == bookType.strip())
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())

            # Step 2: Add date filter based on check (same as original)
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
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                    logger.debug(f"Applying date range filter: {start_date} to {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid date format for startDate or endDate: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            else:
                filters.append(BookFollowUpTable.currentDate.is_(None))
                logger.debug("Applying currentDate IS NULL filter")

            # Step 3: Fetch records (same as original)
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

            # Step 4: Calculate department statistics with explicit handling
            logger.info("Calculating department statistics...")
            
            # First, get raw counts to debug
            raw_count_stmt = (
                select(
                    BookFollowUpTable.deID,
                    func.count(BookFollowUpTable.id).label('count')
                )
                .filter(*filters)
                .group_by(BookFollowUpTable.deID)
            )
            
            raw_result = await db.execute(raw_count_stmt)
            raw_counts = raw_result.fetchall()
            logger.info(f"Raw deID counts: {[(row.deID, row.count) for row in raw_counts]}")
            
            # Then get department details
            stats_stmt = (
                select(
                    BookFollowUpTable.deID,
                    Department.departmentName,
                    Committee.Com,
                    func.count(BookFollowUpTable.id).label('count')
                )
                .outerjoin(Department, cast(BookFollowUpTable.deID, String) == cast(Department.deID, String))
                .outerjoin(Committee, Department.coID == Committee.coID)
                .filter(*filters)
                .group_by(
                    BookFollowUpTable.deID, 
                    Department.departmentName, 
                    Committee.Com
                )
                .order_by(func.count(BookFollowUpTable.id).desc())
            )

            stats_result = await db.execute(stats_stmt)
            stats_rows = stats_result.fetchall()

            # Step 5: Format records
            records = [
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
                    "deID": str(row.deID) if row.deID is not None else None,  # Convert to string
                    "Com": row.Com,
                    "departmentName": row.departmentName,
                }
                for row in rows
            ]

            # Step 6: Format statistics
            department_stats = [
                {
                    "deID": str(stat_row.deID) if stat_row.deID is not None else "unknown",  # Convert to string
                    "departmentName": stat_row.departmentName or "غير محدد",
                    "Com": stat_row.Com or "غير محدد",
                    "count": stat_row.count
                }
                for stat_row in stats_rows
            ]

            # Calculate totals
            total_records = len(records)
            total_departments = len(department_stats)

            return {
                "records": records,
                "statistics": {
                    "totalRecords": total_records,
                    "totalDepartments": total_departments,
                    "departmentBreakdown": department_stats,
                    "filters": {
                        "bookType": bookType,
                        "bookStatus": bookStatus,
                        "dateRangeEnabled": check,
                        "startDate": startDate if check else None,
                        "endDate": endDate if check else None
                    }
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reportBookFollowUpWithStats: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving filtered report with statistics.")
        












    @staticmethod
    async def reportBookFollowUpWithStats(
        db: AsyncSession,
        bookType: Optional[str] = None,
        bookStatus: Optional[str] = None,
        check: Optional[bool] = False,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns a filtered list of bookFollowUp records with multi-department statistics.
        Single committee with multiple departments per book.
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
                    
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                    logger.debug(f"Applying date range filter: {start_date} to {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid date format for startDate or endDate: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            else:
                filters.append(BookFollowUpTable.currentDate.is_(None))
                logger.debug("Applying currentDate IS NULL filter")

            # Step 3: Fetch matching records with primary junction info
            stmt = (
                select(
                    BookFollowUpTable.id,
                    BookFollowUpTable.bookType,
                    BookFollowUpTable.bookNo,
                    BookFollowUpTable.bookDate,
                    BookFollowUpTable.directoryName,
                    BookFollowUpTable.junctionID,
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
                    # Primary committee and department from junction
                    Committee.coID,
                    Committee.Com,
                    Department.deID,
                    Department.departmentName
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(
                    CommitteeDepartmentsJunction,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .outerjoin(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                .outerjoin(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                .filter(*filters)
                .order_by(BookFollowUpTable.bookNo)
            )

            result = await db.execute(stmt)
            rows = result.fetchall()

            # Step 4: Get book IDs for multi-department queries
            book_ids = [row.id for row in rows]
            
            # Step 5: Get all departments for each book (single committee, multiple departments)
            dept_map = {}
            if book_ids:
                dept_query = select(
                    BookFollowUpTable.id.label('book_id'),
                    Department.deID,
                    Department.departmentName,
                    Committee.coID,
                    Committee.Com
                ).select_from(BookFollowUpTable).join(
                    BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID
                ).join(
                    CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id
                ).join(
                    Committee, CommitteeDepartmentsJunction.coID == Committee.coID
                ).join(
                    Department, CommitteeDepartmentsJunction.deID == Department.deID
                ).filter(BookFollowUpTable.id.in_(book_ids))
                
                dept_result = await db.execute(dept_query)
                dept_rows = dept_result.fetchall()
                
                for dept_row in dept_rows:
                    book_id = dept_row.book_id
                    if book_id not in dept_map:
                        dept_map[book_id] = []
                    dept_map[book_id].append({
                        "deID": dept_row.deID,
                        "departmentName": dept_row.departmentName,
                        "coID": dept_row.coID,
                        "Com": dept_row.Com
                    })

            # Step 6: Calculate department statistics
            logger.info("Calculating multi-department statistics...")
            
            # Count books per department (a book with 2 departments counts once for each)
            department_counts = {}
            for book_id, departments in dept_map.items():
                for dept in departments:
                    dept_key = (dept['deID'], dept['departmentName'], dept['Com'])
                    if dept_key not in department_counts:
                        department_counts[dept_key] = 0
                    department_counts[dept_key] += 1
            
            # Format department statistics
            department_stats = [
                {
                    "deID": str(dept_key[0]) if dept_key[0] else "unknown",
                    "departmentName": dept_key[1] or "غير محدد",
                    "Com": dept_key[2] or "غير محدد",
                    "count": count
                }
                for dept_key, count in sorted(
                    department_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]

            # Step 7: Format records with multi-department info
            records = []
            for idx, row in enumerate(rows):
                all_departments = dept_map.get(row.id, [])
                
                # Create department summary
                dept_names = [dept["departmentName"] for dept in all_departments if dept["departmentName"]]
                department_names = ", ".join(dept_names) if dept_names else row.departmentName
                
                records.append({
                    "serialNo": idx + 1,
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
                    
                    # Single committee info
                    "coID": row.coID,
                    "Com": row.Com,
                    "deID": str(row.deID) if row.deID else None,
                    "departmentName": row.departmentName,
                    
                    # Multi-department info
                    "all_departments": all_departments,
                    "department_names": department_names,
                    "department_count": len(all_departments)
                })

            # Calculate totals
            total_records = len(records)
            total_departments = len(department_stats)
            
            # Calculate books per committee (should be one committee now)
            committee_stats = {}
            for book_id, departments in dept_map.items():
                if departments:
                    com_name = departments[0]['Com']  # All departments have same committee
                    if com_name:
                        committee_stats[com_name] = committee_stats.get(com_name, 0) + 1

            committee_breakdown = [
                {"committeeName": com_name, "count": count}
                for com_name, count in sorted(
                    committee_stats.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            ]

            logger.info(f"Report with stats generated: {total_records} records, {total_departments} departments")
            
            return {
                "records": records,
                "statistics": {
                    "totalRecords": total_records,
                    "totalDepartments": total_departments,
                    "totalCommittees": len(committee_breakdown),
                    "departmentBreakdown": department_stats,
                    "committeeBreakdown": committee_breakdown,
                    "filters": {
                        "bookType": bookType,
                        "bookStatus": bookStatus,
                        "dateRangeEnabled": check,
                        "startDate": startDate if check else None,
                        "endDate": endDate if check else None
                    }
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reportBookFollowUpWithStats: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error retrieving filtered report with statistics.")
        
# check this and deleted 
    @staticmethod
    async def getDepartmentStatistics(
        db: AsyncSession,
        bookType: Optional[str] = None,
        bookStatus: Optional[str] = None,
        check: Optional[bool] = False,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns only department statistics without the full record list.
        Useful for dashboard widgets or summary views.
        """
        try:
            # Build same filters as main method
            filters = []
            if bookType:
                filters.append(BookFollowUpTable.bookType == bookType.strip())
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())

            # Apply same date filtering logic as main method
            if check and startDate and endDate:
                try:
                    start_date = datetime.strptime(startDate, '%Y-%m-%d').date()
                    end_date = datetime.strptime(endDate, '%Y-%m-%d').date()
                    if start_date > end_date:
                        raise HTTPException(status_code=400, detail="startDate cannot be after endDate")
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            elif not check and not startDate and not endDate:
                filters.append(BookFollowUpTable.currentDate.is_(None))
            elif startDate and endDate:
                try:
                    start_date = datetime.strptime(startDate, '%Y-%m-%d').date()
                    end_date = datetime.strptime(endDate, '%Y-%m-%d').date()
                    if start_date > end_date:
                        raise HTTPException(status_code=400, detail="startDate cannot be after endDate")
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

            # Get department statistics
            stats_stmt = (
                select(
                    BookFollowUpTable.deID,
                    Department.departmentName,
                    Committee.Com,
                    func.count(BookFollowUpTable.id).label('count')
                )
                .outerjoin(Department, BookFollowUpTable.deID == Department.deID)
                .outerjoin(Committee, Department.coID == Committee.coID)
                .filter(*filters)
                .group_by(
                    BookFollowUpTable.deID, 
                    Department.departmentName, 
                    Committee.Com
                )
                .order_by(func.count(BookFollowUpTable.id).desc())
            )

            stats_result = await db.execute(stats_stmt)
            stats_rows = stats_result.fetchall()

            # Get total count
            total_stmt = select(func.count(BookFollowUpTable.id)).filter(*filters)
            total_result = await db.execute(total_stmt)
            total_records = total_result.scalar() or 0

            department_stats = [
                {
                    "deID": str(stat_row.deID) if stat_row.deID is not None else "unknown",
                    "departmentName": stat_row.departmentName or "غير محدد",
                    "Com": stat_row.Com or "غير محدد",
                    "count": stat_row.count,
                    "percentage": round((stat_row.count / total_records * 100), 2) if total_records > 0 else 0
                }
                for stat_row in stats_rows
            ]

            return {
                "totalRecords": total_records,
                "totalDepartments": len(department_stats),
                "departmentBreakdown": department_stats,
                "filters": {
                    "bookType": bookType,
                    "bookStatus": bookStatus,
                    "dateRangeEnabled": check,
                    "startDate": startDate if check else None,
                    "endDate": endDate if check else None
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in getDepartmentStatistics: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving department statistics.")

 
    @staticmethod
    async def reportBookFollowUpByDepartment(
        db: AsyncSession,
        bookType: Optional[str] = None,
        bookStatus: Optional[str] = None,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None,
        coID: Optional[str] = None,
        deID: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Returns a filtered list of bookFollowUp records by department and committee.
        
        Args:
            db: AsyncSession for database access
            bookType: Optional filter for book type
            bookStatus: Optional filter for book status
            startDate: Start date for filtering (YYYY-MM-DD)
            endDate: End date for filtering (YYYY-MM-DD)
            coID: Optional filter for committee ID
            deID: Optional filter for department ID

        Returns:
            Dictionary containing records, total, and department/committee info
        """
        try:
            # Step 1: Build filters
            filters = []
            if bookType:
                filters.append(BookFollowUpTable.bookType == bookType.strip())
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())

            # Step 2: Add date filter if dates are provided
            if startDate and endDate:
                try:
                    start_date = datetime.strptime(startDate, '%Y-%m-%d').date()
                    end_date = datetime.strptime(endDate, '%Y-%m-%d').date()
                    if start_date > end_date:
                        logger.error("startDate cannot be after endDate")
                        raise HTTPException(status_code=400, detail="startDate cannot be after endDate")
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                    logger.debug(f"Applying date range filter: {start_date} to {end_date}")
                except ValueError as e:
                    logger.error(f"Invalid date format for startDate or endDate: {str(e)}")
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

            # Step 3: Build main query joining through junction table
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
                    Department.deID,
                    Department.departmentName,
                    Committee.Com,
                    Committee.coID
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .outerjoin(
                    CommitteeDepartmentsJunction,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .outerjoin(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                .outerjoin(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                .order_by(BookFollowUpTable.currentDate)
            )
            
            # Apply department filter via junction
            if deID:
                filters.append(Department.deID == int(deID.strip()))
                logger.debug(f"Applying department filter: deID={deID}")
            
            # Apply committee filter via junction
            if coID:
                filters.append(Committee.coID == int(coID.strip()))
                logger.debug(f"Applying committee filter: coID={coID}")
            
            # Apply filters and execute query
            result = await db.execute(stmt.filter(*filters).order_by(BookFollowUpTable.bookNo))
            rows = result.fetchall()

            # Step 4: Get Department and Committee info based on filters
            com_name = None
            dept_name = None

            if deID or coID:
                # Query for specific department/committee info
                dept_query = (
                    select(Department.departmentName, Committee.Com)
                    .join(CommitteeDepartmentsJunction, Department.deID == CommitteeDepartmentsJunction.deID)
                    .join(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                )
                
                if deID:
                    dept_query = dept_query.where(Department.deID == int(deID.strip()))
                if coID:
                    dept_query = dept_query.where(Committee.coID == int(coID.strip()))
                
                dept_result = await db.execute(dept_query)
                dept_info = dept_result.first()
                
                if dept_info:
                    dept_name = dept_info.departmentName
                    com_name = dept_info.Com
                    logger.debug(f"Found department info - Com: {com_name}, Department: {dept_name}")

            # Step 5: Format records
            records = []
            total_records = len(rows)

            for i, row in enumerate(rows):
                records.append({
                    "serialNo": i + 1,
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
                    "deID": str(row.deID) if row.deID is not None else None,
                    "Com": row.Com,
                    "departmentName": row.departmentName,
                })

            logger.info(f"Found {len(records)} records matching filters")

            # Step 6: Return structured response with department/committee info
            return {
                "records": records,
                "total": total_records,
                "Com": com_name,
                "departmentName": dept_name
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in reportBookFollowUpByDepartment: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error retrieving filtered department records.")




    @staticmethod
    async def getAllCommitteesWithDepartments(
        db: AsyncSession,
        bookStatus: Optional[str] = None,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None,
        coID: Optional[str] = None,
        deID: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all unique committees that have books in BookFollowUpTable with filtering,
        along with all their associated departments.
        
        Args:
            bookStatus: Optional filter for book status
            startDate: Optional start date for filtering (YYYY-MM-DD)
            endDate: Optional end date for filtering (YYYY-MM-DD)
            coID: Optional filter for specific committee
            deID: Optional filter for specific department
        
        Returns:
            List of dictionaries containing committee info with nested departments
        """
        try:
            # Build filters
            filters = []
            
            # Book status filter
            if bookStatus:
                filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())
            
            # Date range filter
            if startDate and endDate:
                try:
                    start_date = datetime.strptime(startDate, '%Y-%m-%d').date()
                    end_date = datetime.strptime(endDate, '%Y-%m-%d').date()
                    if start_date > end_date:
                        raise HTTPException(status_code=400, detail="startDate cannot be after endDate")
                    filters.append(BookFollowUpTable.currentDate.isnot(None))
                    filters.append(BookFollowUpTable.currentDate.between(start_date, end_date))
                except ValueError as e:
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
            
            # Committee filter
            if coID:
                filters.append(Committee.coID == int(coID.strip()))
            
            # Department filter
            if deID:
                filters.append(Department.deID == int(deID.strip()))
            
            # Query to get all committees with their departments through junction
            stmt = (
                select(
                    Committee.coID,
                    Committee.Com,
                    Department.deID,
                    Department.departmentName
                )
                .distinct()
                .join(
                    CommitteeDepartmentsJunction,
                    Committee.coID == CommitteeDepartmentsJunction.coID
                )
                .join(
                    Department,
                    Department.deID == CommitteeDepartmentsJunction.deID
                )
                .join(
                    BookFollowUpTable,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .where(
                    and_(
                        BookFollowUpTable.id.isnot(None),
                        *filters
                    )
                )
                .order_by(Committee.Com, Department.departmentName)
            )
            
            result = await db.execute(stmt)
            rows = result.fetchall()
            
            # Group departments by committee
            committees_dict = {}
            for row in rows:
                co_id = str(row.coID)
                
                if co_id not in committees_dict:
                    committees_dict[co_id] = {
                        "coID": co_id,
                        "Com": row.Com,
                        "departments": []
                    }
                
                # Add department if not already added
                dept_exists = any(
                    dept["deID"] == str(row.deID) 
                    for dept in committees_dict[co_id]["departments"]
                )
                
                if not dept_exists and row.deID is not None:
                    committees_dict[co_id]["departments"].append({
                        "deID": str(row.deID),
                        "departmentName": row.departmentName
                    })
            
            # Convert to list
            committees = list(committees_dict.values())
            
            logger.info(
                f"Found {len(committees)} committees with departments "
                f"(filters: bookStatus={bookStatus}, dates={startDate} to {endDate}, "
                f"coID={coID}, deID={deID})"
            )
            return committees
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in getAllCommitteesWithDepartments: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error retrieving committees with departments.")



    @staticmethod
    async def getDepartmentsByCommittee(
        db: AsyncSession,
        coID: str
    ) -> Dict[str, Any]:
        """
        Get all departments for a specific committee that have books in BookFollowUpTable.
        
        Args:
            coID: Committee ID to filter by
            
        Returns:
            Dictionary with committee info and its departments
        """
        try:
            # Query to get committee info with its departments
            stmt = (
                select(
                    Committee.coID,
                    Committee.Com,
                    Department.deID,
                    Department.departmentName
                )
                .distinct()
                .join(
                    CommitteeDepartmentsJunction,
                    Committee.coID == CommitteeDepartmentsJunction.coID
                )
                .join(
                    Department,
                    Department.deID == CommitteeDepartmentsJunction.deID
                )
                .join(
                    BookFollowUpTable,
                    BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
                )
                .where(
                    and_(
                        Committee.coID == int(coID.strip()),
                        BookFollowUpTable.id.isnot(None)
                    )
                )
                .order_by(Department.departmentName)
            )
            
            result = await db.execute(stmt)
            rows = result.fetchall()
            
            if not rows:
                logger.warning(f"No departments found for committee coID={coID}")
                raise HTTPException(
                    status_code=404, 
                    detail=f"No departments found for committee with coID={coID}"
                )
            
            # Extract committee info (same for all rows)
            committee_info = {
                "coID": str(rows[0].coID),
                "Com": rows[0].Com
            }
            
            # Extract departments
            departments = []
            for row in rows:
                if row.deID is not None:
                    departments.append({
                        "deID": str(row.deID),
                        "departmentName": row.departmentName
                    })
            
            logger.info(f"Found {len(departments)} departments for committee coID={coID}")
            
            return {
                **committee_info,
                "departments": departments,
                "totalDepartments": len(departments)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in getDepartmentsByCommittee: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error retrieving departments for committee.")