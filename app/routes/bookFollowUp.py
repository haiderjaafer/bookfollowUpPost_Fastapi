import asyncio
from datetime import date, datetime,timedelta, timezone
from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Form, Depends
import pydantic
from sqlalchemy import select,extract,func, text
from sqlalchemy.ext.asyncio import AsyncSession  #  Use AsyncSession instead of sync Session
from app.database.database import get_async_db  #  Import async DB dependency
from app.models.architecture.committees import Committee, CommitteeResponse
from app.models.architecture.department import Department, DepartmentNameResponse
from app.models.users import Users
from app.services.bookFollowUp import BookFollowUpService
from app.services.pdf_service import PDFService
from app.helper.save_pdf import async_delayed_delete, save_pdf_to_server  #  Responsible for saving the uploaded file
from app.database.config import settings
from app.models.PDFTable import PDFCreate, PDFResponse, PDFTable
from app.models.bookFollowUpTable import BookFollowUpCreate, BookFollowUpResponse, BookFollowUpTable, BookFollowUpUpdate, BookFollowUpWithPDFResponseForUpdateByBookID, BookStatusCounts, BookTypeCounts, PaginatedOrderOut, SubjectRequest, UserBookCount
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date
from app.services.lateBooks import LateBookFollowUpService
from fastapi.responses import FileResponse
import os
from urllib.parse import unquote
import logging
from pydantic import BaseModel

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:  # Avoid duplicate handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

#  Create router with a prefix and tag for grouping endpoints
bookFollowUpRouter = APIRouter(prefix="/api/bookFollowUp", tags=["BookFollowUp"])



# Updated Route
@bookFollowUpRouter.post("")
async def add_book_with_pdf(
    bookNo: str = Form(...),
    bookDate: str = Form(...),
    bookType: str = Form(...),
    directoryName: str = Form(...),
    coID: int = Form(...),  # Single Committee ID
    deIDs: str = Form(...),  # Comma-separated Department IDs: "11,15,21"
    incomingNo: str = Form(...),
    incomingDate: str = Form(...),
    subject: str = Form(...),
    bookAction: str = Form(...),
    bookStatus: str = Form(...),
    notes: str = Form(...),
    userID: str = Form(...),
    file: UploadFile = Form(...),
    username: str = Form(),
    db: AsyncSession = Depends(get_async_db)
):
    try:
        # Step 1: Parse department IDs
        department_ids = [int(dept_id.strip()) for dept_id in deIDs.split(',')]
        print(f"Committee {coID} will be associated with departments: {department_ids}")
        
        # Step 2: Get or create multiple junctions for committee-department pairs
        junction_ids = []
        for dept_id in department_ids:
            junction_id = await BookFollowUpService.get_or_create_junction(db, coID, dept_id)
            junction_ids.append(junction_id)
            print(f"Junction ID for Committee {coID} + Department {dept_id}: {junction_id}")
        
        # Step 3: Create book data (use first junction as primary reference)
        book_data = BookFollowUpCreate(
            bookNo=bookNo,
            bookDate=bookDate,
            bookType=bookType,
            directoryName=directoryName,
            incomingNo=incomingNo,
            incomingDate=incomingDate,
            subject=subject,
            destination="destination",
            bookAction=bookAction,
            bookStatus=bookStatus,
            notes=notes,
            currentDate=datetime.today().strftime('%Y-%m-%d'),
            userID=userID,
            junctionID=junction_ids[0]  # Primary junction reference
        )
        
        print(f"book_data...........: {book_data}")
        # Step 4: Insert book
        book_id = await BookFollowUpService.insert_book(db, book_data)
        print(f"Inserted book with ID: {book_id}")
        
        # Step 5: Create bridge records for ALL departments (many-to-many)
        bridge_ids = []
        for junction_id in junction_ids:
            bridge_id = await BookFollowUpService.create_book_junction_bridge(db, book_id, junction_id)
            bridge_ids.append(bridge_id)
            print(f"Created bridge record {bridge_id} for book {book_id} and junction {junction_id}")
        
        # Step 6: Handle PDF processing (existing logic)
        count = await PDFService.get_pdf_count(db, book_id)
        print(f"PDF count for book {book_id}: {count}")
        
        # Save file
        upload_dir = settings.PDF_UPLOAD_PATH
        with file.file as f:
            pdf_path = save_pdf_to_server(f, bookNo, bookDate, count, upload_dir)
        print(f"Saved PDF to: {pdf_path}")
        
        # Close upload stream
        file.file.close()
        
        # Insert PDF record
        pdf_data = PDFCreate(
            bookID=book_id,
            bookNo=bookNo,
            countPdf=count,
            pdf=pdf_path,
            userID=userID,
            currentDate=datetime.now().date().isoformat()
        )
        await PDFService.insert_pdf(db, pdf_data)
        print(f"Inserted PDF record: {pdf_path}")
        
        # Delete original file (with delay)
        scanner_path = os.path.join(settings.PDF_SOURCE_PATH, username, file.filename)
        print(f"Attempting to delete: {scanner_path}")
        if os.path.isfile(scanner_path):
            asyncio.create_task(async_delayed_delete(scanner_path, delay_sec=3))
        else:
            print(f"File not found for deletion: {scanner_path}")
        
        return {
            "message": "Book and PDF saved successfully with multiple departments", 
            "bookID": book_id,
            "committee_id": coID,
            "department_ids": department_ids,
            "junction_ids": junction_ids,
            "bridge_ids": bridge_ids
        }
        
    except Exception as e:
        print(f"❌ Error in add_book_with_pdf: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    





@bookFollowUpRouter.post("/add-supplement")
async def add_supplement_pdf(
    bookID: int = Form(...),
    bookNo: str = Form(...),
    bookDate: str = Form(...),
    userID: int = Form(...),
    file: UploadFile = Form(...),
    db: AsyncSession = Depends(get_async_db)
):
    print(f"supplement ...")
    # 1. Get current count of pdfs for bookID
    count = await PDFService.get_pdf_count_async(db, bookID)
    
    print(f"supplement count... {count}")
    print(f"supplement bookID... {bookID}")

    # 2. Save PDF to server (increment count for filename)
    upload_dir = settings.PDF_UPLOAD_PATH
   #print(f"upload_dir -PDF_UPLOAD_PATH \env------- {settings.PDF_UPLOAD_PATH}")

    pdf_path = save_pdf_to_server(file.file, bookNo, bookDate, count, upload_dir)

    # print("upload_dir"+ upload_dir)

    # # 3. Insert PDF record with incremented countPdf = count + 1
    pdf_record = PDFCreate(
        bookID=bookID,
        bookNo=bookNo,
        countPdf=count + 1,
        pdf=pdf_path,
        userID=userID,
        currentDate=datetime.now().date()
    )
    await PDFService.insert_pdf(db, pdf_record)
    
    try:
        # This assumes the file has been saved temporarily at the path below
        scanner_path = os.path.join(settings.PDF_SOURCE_PATH, file.filename)
        os.remove(scanner_path)
    except Exception as e:
        print(f"⚠️ Warning: Could not delete original file {scanner_path}. Reason: {e}")

    return {"message": "Supplement PDF added successfully", "pdfCount": count + 1,
            "PDF_UPLOAD_PATH":settings.PDF_UPLOAD_PATH.as_posix()}


   # return {"PDF_UPLOAD_PATH":settings.PDF_UPLOAD_PATH.as_posix()}


@bookFollowUpRouter.get("/test-path")
async def test_path():
    return {
        "PDF_UPLOAD_PATH": settings.PDF_UPLOAD_PATH.as_posix(),
        "PDF_SOURCE_PATH": settings.PDF_SOURCE_PATH.as_posix(),
    }



@bookFollowUpRouter.get("/getAllBooksNo", response_model=list[str])
async def getAllBooksNo(db: AsyncSession = Depends(get_async_db)):
    print("getAllBooksNo ... route")
    return await BookFollowUpService.getAllBooksNo(db)


@bookFollowUpRouter.get("/getAllIncomingNo", response_model=list[Optional[str]])
async def getAllIncomingNo(db: AsyncSession = Depends(get_async_db)):
    return await BookFollowUpService.getAllIncomingNo(db)



@bookFollowUpRouter.get("/getAllDirectoryNames", response_model=list[str])
async def get_all_directory_names(
    search: str = Query(default="", description="Partial match for directoryName"),
    db: AsyncSession = Depends(get_async_db)
):
    return await BookFollowUpService.searchDirectoryNames(db, search)


@bookFollowUpRouter.get("/getSubjects", response_model=list[str])
async def getSubjects(
    search: str = Query(default="", description="Partial match for subject"),
    db: AsyncSession = Depends(get_async_db)
):
    return await BookFollowUpService.getSubjects(db, search)



@bookFollowUpRouter.get("/getDestination", response_model=list[str])
async def getSubjects(
    search: str = Query(default="", description="Partial match for destination"),
    db: AsyncSession = Depends(get_async_db)
):
    return await BookFollowUpService.getDestination(db, search)






@bookFollowUpRouter.get("/getAll", response_model=Dict[str, Any])
async def getByFilterBooksNo(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    bookNo: Optional[str] = Query(None),
    bookStatus: Optional[str] = Query(None),
    bookType: Optional[str] = Query(None),
    directoryName: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    incomingNo: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    return await BookFollowUpService.getAllFilteredBooksNo(
        request, db, page, limit, bookNo, bookStatus, bookType, directoryName,subject, incomingNo
    )




@bookFollowUpRouter.get("/checkBookNoExistsForDebounce")
async def check_order_exists(
    bookType: str = Query(..., alias="bookType"),  # Required query parameter for book type
    bookNo: str = Query(..., alias="bookNo"),      # Required query parameter for book number
    bookDate: str = Query(..., alias="bookDate"),  # Required query parameter for full date (YYYY-MM-DD)
    db: AsyncSession = Depends(get_async_db),      # Async database session dependency
):
    """
    Check if a book record exists based on bookType, bookNo, and the year of bookDate.
    Expects bookDate as YYYY-MM-DD, extracts the year, and matches against the year of bookDate in the database.
    Returns {"exists": true} if found, {"exists": false} otherwise.
    """
    print("checkBookNoExistsForDebounce")  # Debug log to confirm endpoint is hit
    print(f"Received: bookType={bookType}, bookNo={bookNo}, bookDate={bookDate}")  # Debug input values

    # Validate and extract year from bookDate
    try:
        # Parse the input date to ensure it's in YYYY-MM-DD format//// Validation: Uses datetime.strptime to parse the date and validate the format
        parsed_date = datetime.strptime(bookDate.strip(), "%Y-%m-%d")
        year = parsed_date.year  # Extract the year
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD (e.g., 2025-06-08)")

    # Build async query to check for existence
    query = select(BookFollowUpTable).filter(
        BookFollowUpTable.bookType == bookType.strip(),  # Match bookType (strip whitespace)
        BookFollowUpTable.bookNo == bookNo.strip(),      # Match bookNo (strip whitespace)
        extract('year', BookFollowUpTable.bookDate) == year   # this year front-end ... from Match year of bookDate //// SQLAlchemy extract: Uses extract('year', BookFollowUpTable.bookDate) to extract the year from the bookDate column in the database:


    )

    try:
        # Execute query and fetch the first result
        result = await db.execute(query)
        book = result.scalars().first()  # Get the first matching record (or None if none found)
        print(f"Query result: {book}")  # Debug query result
        return {"exists": bool(book)}  # Return existence as boolean
    except Exception as e:
        print(f"Database error: {str(e)}")  # Debug database errors
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@bookFollowUpRouter.get("/lateBooks", response_model=Dict[str, Any])
async def get_late_books(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    userID: int = Query(..., description="get late books per userID"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Retrieve late books (status 'قيد الانجاز') with pagination filtered by userID.
    Returns paginated data with total count, page, limit, and total pages.
    """
    try:
        logger.info(f"GET /lateBooks - userID: {userID}, page: {page}, limit: {limit}")
        result = await LateBookFollowUpService.getLateBooks(db, page, limit, userID)
        logger.info(f"Route response: {len(result.get('data', []))} records")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_late_books route: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@bookFollowUpRouter.get("/pdf/{book_no}", response_model=List[PDFResponse])
async def get_pdfs_by_book_no(book_no: str, db: AsyncSession = Depends(get_async_db)):
    print(f"Fetching PDFs for bookNo: {book_no}")
    try:
        query = (
            select(
                PDFTable.id,
                PDFTable.pdf,
                PDFTable.bookNo,
                PDFTable.currentDate,
                Users.username
            )
            .outerjoin(Users, PDFTable.userID == Users.id)
            .filter(PDFTable.bookNo == book_no)
        )
        print("Executing query...")
        result = await db.execute(query)
        print("Query executed, fetching results...")
        pdf_records = result.fetchall()
        print(f"Fetched {len(pdf_records)} records")
        
        pdfs = [
            {
                "id": record.id,
                "pdf": record.pdf,
                "bookNo": record.bookNo,
                "currentDate": record.currentDate.strftime('%Y-%m-%d') if record.currentDate else None,
                "username": record.username if record.username else None
            }
            for record in pdf_records
        ]
        
        print(f"Returning {len(pdfs)} PDFs for bookNo: {book_no}")

        return pdfs  # Returns [] if no records
    
    except Exception as e:
        print(f"Error fetching PDFs for bookNo {book_no}: {str(e)}")
        print("Traceback:", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")



@bookFollowUpRouter.get("/pdf/file/{pdf_id}")
async def get_pdf_file(pdf_id: int, db: AsyncSession = Depends(get_async_db)):

    """
    Retrieve a single PDF file by its ID from PDFTable.
    Returns the PDF file if found and accessible.
    """
    print(f"Fetching PDF file with id: {pdf_id}")
    try:
        query = select(
            PDFTable.pdf,
            PDFTable.bookNo,
            PDFTable.userID
        ).filter(PDFTable.id == pdf_id)
        result = await db.execute(query)
        pdf_record = result.first()
        
        if not pdf_record:
            print(f"No PDF found for id: {pdf_id}")
            raise HTTPException(status_code=404, detail="PDF record not found in database")
        
        pdf_path, book_no, user_id = pdf_record
        print(f"Queried PDF path: {pdf_path}, bookNo: {book_no}, userID: {user_id}")
        
        if not os.path.exists(pdf_path):
            print(f"PDF file does not exist at: {pdf_path}")
            raise HTTPException(status_code=404, detail="PDF file not found on server")
        
        print(f"Serving PDF file: {pdf_path} for bookNo: {book_no}, userID: {user_id}")
        return FileResponse(pdf_path, media_type="application/pdf")
    except Exception as e:
        print(f"Error fetching PDF file with id {pdf_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    




# Updated JSON PATCH Route with Multi-Department Support
@bookFollowUpRouter.patch("/{id}/json", response_model=Dict[str, Any])
async def update_book_json(
    id: int,
    book_data: BookFollowUpUpdate,  # Use updated model
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update a book record by ID using JSON data with multi-department support (no file upload).
    
    Args:
        id: Book ID to update.
        book_data: Pydantic model with update fields including multi-department support.
        db: Database session.
        
    Returns:
        JSON response with update results and multi-department information.
    """
    try:
        logger.info(f"JSON update for book ID {id}: {book_data}")
        
        # Extract multi-department fields
        committee_id = book_data.coID
        deIDs_str = book_data.deIDs
        
        # Parse department IDs
        department_ids = []
        if deIDs_str:
            try:
                if isinstance(deIDs_str, str):
                    # Handle comma-separated string: "11,15,21"
                    if deIDs_str.strip().startswith('['):
                        # Handle JSON array string: "[11,15,21]"
                        import json
                        department_ids = json.loads(deIDs_str)
                    else:
                        # Handle comma-separated string
                        department_ids = [int(dept_id.strip()) for dept_id in deIDs_str.split(',') if dept_id.strip()]
                logger.info(f"Parsed department IDs: {department_ids}")
            except (ValueError, json.JSONDecodeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid department IDs format: {deIDs_str}")

        # Validate committee and departments relationship
        if committee_id and department_ids:
            logger.info(f"JSON update with multi-department: Committee {committee_id} with departments {department_ids}")
        elif committee_id or department_ids:
            if committee_id and not department_ids:
                raise HTTPException(status_code=400, detail="Department IDs required when committee ID is provided")
            elif department_ids and not committee_id:
                raise HTTPException(status_code=400, detail="Committee ID required when department IDs are provided")

        # Convert to BookFollowUpCreate (excluding multi-department fields)
        create_data_dict = book_data.model_dump(exclude_none=True, exclude={'coID', 'deIDs'})
        create_data = BookFollowUpCreate(**create_data_dict)
        
        # Call updated service method with multi-department support
        result = await BookFollowUpService.update_book_with_multi_departments(
            db=db,
            id=id,
            book_data=create_data,
            committee_id=committee_id,
            department_ids=department_ids if department_ids else None,
            file=None,
            user_id=book_data.userID,
            username=None
        )

        return {
            "message": "Book updated successfully via JSON",
            "bookID": result["book_id"],
            "committee_id": result.get("committee_id"),
            "department_ids": result.get("department_ids"),
            "junction_ids": result.get("junction_ids"),
            "bridge_ids": result.get("bridge_ids"),
            "total_departments": result.get("total_departments", 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in JSON update for ID {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# Updated main PATCH route to handle both file and non-file scenarios
@bookFollowUpRouter.patch("/{id}", response_model=Dict[str, Any])
async def update_book_with_pdf(
    id: int,
    bookNo: Optional[str] = Form(None),
    bookDate: Optional[str] = Form(None),
    bookType: Optional[str] = Form(None),
    directoryName: Optional[str] = Form(None),
    incomingNo: Optional[str] = Form(None),
    incomingDate: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    destination: Optional[str] = Form(None),
    bookAction: Optional[str] = Form(None),
    bookStatus: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    userID: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    coID: Optional[str] = Form(None),  # Committee ID
    deIDs: Optional[str] = Form(None),  # Comma-separated department IDs
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update a book record by ID with optional file upload and multi-department support.
    Handles both scenarios: with file upload and without file upload.
    
    Args:
        id: Path parameter for the book ID.
        bookNo, bookDate, ...: Optional form fields to update.
        userID: Optional user ID for book and PDF.
        coID: Committee ID for junction management.
        deIDs: Comma-separated department IDs (e.g., "11,15,21").
        file: Optional PDF file to add.
        db: Async SQLAlchemy session.
        
    Returns:
        JSON response with success message, updated book ID, and junction details.
    """
    try:
        logger.info(f"Updating book ID {id} with data: bookNo={bookNo}, userID={userID}, coID={coID}, deIDs={deIDs}, file={file.filename if file else None}")
        
        # Validate at least one field or file is provided
        form_fields = [
            bookNo, bookDate, bookType, directoryName, incomingNo,
            incomingDate, subject, destination, bookAction, bookStatus,
            notes, userID, coID, deIDs
        ]
        
        # Check if we have a valid file
        has_file = file is not None and hasattr(file, 'filename') and file.filename
        
        # Check if we have at least one form field with a value
        has_form_data = any(v is not None and str(v).strip() != '' for v in form_fields)
        
        if not has_form_data and not has_file:
            raise HTTPException(status_code=400, detail="At least one field or file must be provided")

        # Parse department IDs if provided
        department_ids = []
        if deIDs and deIDs.strip():
            try:
                department_ids = [int(dept_id.strip()) for dept_id in deIDs.split(',') if dept_id.strip()]
                logger.info(f"Parsed department IDs: {department_ids}")
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid department IDs format: {deIDs}")

        # Parse committee ID
        committee_id = None
        if coID and coID.strip():
            try:
                committee_id = int(coID)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid committee ID: {coID}")

        # Validate committee and departments relationship
        if committee_id and department_ids:
            logger.info(f"Updating with multi-department assignment: Committee {committee_id} with departments {department_ids}")
        elif committee_id or department_ids:
            if committee_id and not department_ids:
                raise HTTPException(status_code=400, detail="Department IDs required when committee ID is provided")
            elif department_ids and not committee_id:
                raise HTTPException(status_code=400, detail="Committee ID required when department IDs are provided")

        # Create book data model (excluding junction-related fields)
        book_data = BookFollowUpCreate(
            bookNo=bookNo,
            bookDate=bookDate,
            bookType=bookType,
            directoryName=directoryName,
            incomingNo=incomingNo,
            incomingDate=incomingDate,
            subject=subject,
            destination=destination,
            bookAction=bookAction,
            bookStatus=bookStatus,
            notes=notes,
            userID=int(userID) if userID else None
        )

        logger.debug(f"Book data created: {book_data}")

        # Call service method with multi-department support
        result = await BookFollowUpService.update_book_with_multi_departments(
            db=db,
            id=id,
            book_data=book_data,
            committee_id=committee_id,
            department_ids=department_ids if department_ids else None,
            file=file if has_file else None,
            user_id=int(userID) if userID else None,
            username=username
        )

        return {
            "message": "Book updated successfully" + (" with file" if has_file else ""),
            "bookID": result["book_id"],
            "committee_id": result.get("committee_id"),
            "department_ids": result.get("department_ids"),
            "junction_ids": result.get("junction_ids"),
            "bridge_ids": result.get("bridge_ids"),
            "pdf_added": result.get("pdf_added", False),
            "total_departments": result.get("total_departments", 0)
        }

    except ValueError as e:
        logger.error(f"Invalid input for ID {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_book_with_pdf for ID {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")



# You'll also need this Pydantic model
# class BookFollowUpUpdate(pydantic.BaseModel):
#     bookNo: Optional[str] = None
#     bookDate: Optional[str] = None
#     bookType: Optional[str] = None
#     directoryName: Optional[str] = None
#     incomingNo: Optional[str] = None
#     incomingDate: Optional[str] = None
#     subject: Optional[str] = None
#     destination: Optional[str] = None
#     bookAction: Optional[str] = None
#     bookStatus: Optional[str] = None
#     notes: Optional[str] = None
#     userID: Optional[int] = None
#     selectedCommittee: Optional[int] = None
#     deID: Optional[int] = None


@bookFollowUpRouter.get("/getBookFollowUpByBookID/{id}", response_model=BookFollowUpWithPDFResponseForUpdateByBookID)
async def get_book_with_pdfs(
    id: int,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Fetch a book by ID with all fields, associated PDFs, PDF count, username, and multi-department support.
    Args:
        id: Book ID to fetch.
        db: Async SQLAlchemy session.
    Returns:
        BookFollowUpWithPDFResponseForUpdateByBookID with book data, PDFs, and all associated departments.
    Raises:
        HTTPException: For missing book or server errors.
    """
    try:
        book_data = await BookFollowUpService.get_book_with_pdfs(db, id)
        return book_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching book ID {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    



    


@bookFollowUpRouter.get("/report", response_model=List[BookFollowUpResponse])
async def get_filtered_report(
    bookType: Optional[str] = Query(None, description="Filter by book type"),
    bookStatus: Optional[str] = Query(None, description="Filter by book status"),
    check: Optional[bool] = Query(False, description="Enable date range filtering (True) or NULL currentDate (False)"),
    startDate: Optional[str] = Query(None, description="Start date (YYYY-MM-DD) for check=True"),
    endDate: Optional[str] = Query(None, description="End date (YYYY-MM-DD) for check=True"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get filtered book follow-up report with multi-department and multi-committee support.
    If check=True, filter by date range. If check=False, filter by currentDate IS NULL.
    
    Returns:
        List of book follow-up records with committee and department information
    """
    logger.debug(f"Received report request: bookType={bookType}, bookStatus={bookStatus}, check={check}, startDate={startDate}, endDate={endDate}")
    return await BookFollowUpService.reportBookFollowUp(db, bookType, bookStatus, check, startDate, endDate)




# Pydantic model for request body
class DeletePDFRequest(pydantic.BaseModel):
    id: int
    pdf: str  # Matches frontend 'pdf' field

# Existing endpoints omitted

@bookFollowUpRouter.delete("/delete_pdf", response_model=dict)
async def delete_pdf(request: DeletePDFRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Deletes a PDFTable record and its associated file based on ID and pdf path.

    Args:
        request: JSON body with id and pdf
        db: Database session

    Returns:
        dict: {"success": true} if deletion succeeds, {"success": false} otherwise
    """
    try:
       # print(request.id)
      #  print(request.pdf)
        success = await PDFService.delete_pdf_record(db, request.id, request.pdf)
        return {"success": success}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_pdf endpoint: {str(e)}")
        return {"success": False}
    


# Specific file path
#file_path = r"D:\booksFollowUp\pdfScanner\book.pdf"

# Route to serve book.pdf
@bookFollowUpRouter.get("/files/book")
async def get_book_pdf(username: str = Query(..., description="Username for the PDF directory")):
    try:
        logger.info(f"Handling request for book.pdf for username: {username}")
                 
        # Construct file path with username instead of hardcoded 'mmm'
        file_path: Path = settings.PDF_SOURCE_PATH / username / "book.pdf"
        # file_path: Path = r"\\\\10.20.11.33\\booksFollowUp\\pdfScanner\\{username}\\book.pdf"
        logger.info(f"Attempting to serve file......: {file_path}")
        logger.info(f"PDF_SOURCE_PATH: {settings.PDF_SOURCE_PATH}")
        logger.info(f"Username directory: {settings.PDF_SOURCE_PATH / username}")
        logger.info(f"Does PDF_SOURCE_PATH exist? {settings.PDF_SOURCE_PATH.exists()}")
        logger.info(f"Does PDF_SOURCE_PATH is dir? {settings.PDF_SOURCE_PATH.is_dir()}")
        logger.info(f"Does username directory exist? {(settings.PDF_SOURCE_PATH / username).exists()}")

        # Validate PDF_SOURCE_PATH
        if not settings.PDF_SOURCE_PATH.exists():
            logger.error(f"PDF_SOURCE_PATH does not exist: {settings.PDF_SOURCE_PATH}")
            raise HTTPException(
                status_code=500,
                detail=f"Server configuration error: PDF source path does not exist ({settings.PDF_SOURCE_PATH})"
            )

        # Validate username directory
        username_dir = settings.PDF_SOURCE_PATH / username
        if not username_dir.exists():
            logger.error(f"Username directory does not exist: {username_dir}")
            raise HTTPException(
                status_code=404,
                detail=f"User directory not found: {username}"
            )

        # Ensure the filename is exactly 'book.pdf'
        if file_path.name.lower() != "book.pdf":
            logger.warning(f"Invalid filename: {file_path.name}")
            raise HTTPException(status_code=404, detail="Only book.pdf is allowed")

        # Check if file actually exists
        if not file_path.is_file():
            logger.warning(f"File not found: {file_path}")
            # Include file path in the error detail for debugging
            raise HTTPException(
                status_code=404,
                detail=f"لا يوجد ملف سكنر book.pdf في المسار: {file_path} للمستخدم: {username}"
            )

        # Check file permissions
        if not os.access(file_path, os.R_OK):
            logger.error(f"No read permission for file: {file_path}")
            raise HTTPException(
                status_code=403,
                detail=f"No read permission for file: {file_path}"
            )

        # Check if file is empty
        if file_path.stat().st_size == 0:
            logger.warning(f"File is empty: {file_path}")
            raise HTTPException(status_code=400, detail="File book.pdf is empty")

        # Verify file is a PDF by checking the magic number
        with open(file_path, 'rb') as f:
            header = f.read(4).decode('latin1')
            if not header.startswith('%PDF'):
                logger.warning(f"File is not a valid PDF: {file_path}")
                raise HTTPException(status_code=400, detail="File is not a valid PDF")

        # Return the PDF file
        logger.info(f"Successfully serving file: {file_path} for user: {username}")
        return FileResponse(
            path=file_path.as_posix(),
            media_type="application/pdf",
            filename="book.pdf"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Server error while serving book.pdf for user {username}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")









@bookFollowUpRouter.get("/counts/book-type", response_model=BookTypeCounts)
async def get_book_type_counts(db: AsyncSession = Depends(get_async_db)):
    try:
        counts = await BookFollowUpService.get_book_type_counts(db)
        return counts
    except Exception as e:
        print(f"Error in get_book_type_counts route: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@bookFollowUpRouter.get("/counts/book-status", response_model=BookStatusCounts)
async def get_book_status_counts(db: AsyncSession = Depends(get_async_db)):
    try:
        counts = await BookFollowUpService.get_book_status_counts(db)
        return counts
    except Exception as e:
        print(f"Error in get_book_status_counts route: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@bookFollowUpRouter.get("/counts/user-books", response_model=List[UserBookCount])
async def get_user_book_counts(db: AsyncSession = Depends(get_async_db)):
    try:
        counts = await BookFollowUpService.get_user_book_counts(db)
        return counts
    except Exception as e:
        print(f"Error in get_user_book_counts route: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    


# GET all committees
@bookFollowUpRouter.get("/committees", response_model=List[CommitteeResponse])
async def get_all_committees(db: AsyncSession = Depends(get_async_db)):
    try:
        logger.info("Fetching all committees")
        # Query all committees
        result = await db.execute(select(Committee))
        committees = result.scalars().all()
        
        if not committees:
            logger.warning("No committees found in the database")
            return []
        
        # Convert to list of Pydantic models
        committees_list = [CommitteeResponse.model_validate(committee) for committee in committees]
        logger.info(f"Retrieved {len(committees_list)} committees")
        return committees_list
    
    except Exception as e:
        logger.error(f"Error fetching committees: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    




# GET department names by coID
@bookFollowUpRouter.get("/{coID}/departments", response_model=List[DepartmentNameResponse])
async def get_department_names_by_coID(coID: int, db: AsyncSession = Depends(get_async_db)):
    try:
        logger.info(f"Fetching department names for coID: {coID}")
        result = await db.execute(select(Committee).filter(Committee.coID == coID))
        committee = result.scalars().first()
        if not committee:
            logger.warning(f"Committee with coID {coID} not found")
            raise HTTPException(status_code=404, detail=f"Committee with coID {coID} not found")
        
        result = await db.execute(select(Department).filter(Department.coID == coID))
        departments = result.scalars().all()
        if not departments:
            logger.warning(f"No departments found for coID {coID}")
            return []
        
        department_names = [
            DepartmentNameResponse(
                deID=department.deID if department.deID is not None else index + 1,
                departmentName=department.departmentName
            )
            for index, department in enumerate(departments)
        ]
        logger.info(f"Retrieved {len(department_names)} department names for coID {coID}")
        return department_names
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching department names for coID {coID}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    



# @bookFollowUpRouter.post("/getRecordBySubject", response_model=Dict[str, Any])
# async def getRecordBySubjectFunction(
#     request: Request,
#     subject: Optional[str] = Query(None),
#     db: AsyncSession = Depends(get_async_db),
# ) -> Dict[str, Any]:
#     if subject:
#         decoded_subject = unquote(subject)
#     #     print(f" subject .......... {decoded_subject}")
#     #     return decoded_subject
#     # return "No subject provided"

#     logger.info(f"Received request for subject: {subject}")
#     return await BookFollowUpService.getRecordBySubject(db, subject)



@bookFollowUpRouter.post("/getRecordBySubject", response_model=Dict[str, Any])
async def getRecordBySubjectFunction(
    request: SubjectRequest,
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    try:
        logger.info(f"Received POST request for subject: {request.subject}")
        logger.info(f"Subject length: {len(request.subject)}")
        return await BookFollowUpService.getRecordBySubject(db, request.subject)
    except Exception as e:
        logger.error(f"Error in POST getRecordBySubject: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# Updated Pydantic Models for Multi-Department Stats Report

class DepartmentInfo(BaseModel):
    """Individual department information"""
    deID: int
    departmentName: str
    coID: int
    Com: str

class BookRecordWithStats(BaseModel):
    """Book record with multi-department support"""
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
    
    # Multi-department fields
    all_departments: List[DepartmentInfo] = []
    department_names: Optional[str] = None
    department_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

class DepartmentStatistic(BaseModel):
    """Department statistics"""
    deID: str
    departmentName: str
    Com: str
    count: int

class CommitteeStatistic(BaseModel):
    """Committee statistics"""
    committeeName: str
    count: int

class ReportFilters(BaseModel):
    """Applied filters"""
    bookType: Optional[str] = None
    bookStatus: Optional[str] = None
    dateRangeEnabled: bool = False
    startDate: Optional[str] = None
    endDate: Optional[str] = None

class ReportStatistics(BaseModel):
    """Report statistics"""
    totalRecords: int
    totalDepartments: int
    totalCommittees: int
    departmentBreakdown: List[DepartmentStatistic]
    committeeBreakdown: List[CommitteeStatistic]
    filters: ReportFilters

class ReportWithStatsResponse(BaseModel):
    """Complete response with records and statistics"""
    records: List[BookRecordWithStats]
    statistics: ReportStatistics
    
    class Config:
        from_attributes = True

    

# New route with statistics
@bookFollowUpRouter.get("/report-with-stats", response_model=ReportWithStatsResponse)
async def get_report_with_statistics(
    bookType: Optional[str] = Query(None),
    bookStatus: Optional[str] = Query(None),
    check: Optional[bool] = Query(False),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db)
):
    return await BookFollowUpService.reportBookFollowUpWithStats(
        db, bookType, bookStatus, check, startDate, endDate
    )


@bookFollowUpRouter.get("/test-dept-counts")
async def test_department_counts(
    bookStatus: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db)
):
    """Test endpoint to check actual department distribution"""
    try:
        # Direct SQL query
        where_clause = "currentDate IS NULL"
        if bookStatus:
            where_clause += f" AND bookStatus = '{bookStatus}'"
            
        sql = f"SELECT deID, COUNT(*) as count FROM bookFollowUpTable WHERE {where_clause} GROUP BY deID ORDER BY deID"
        
        result = await db.execute(text(sql))
        rows = result.fetchall()
        
        return {
            "sql_query": sql,
            "results": [{"deID": row.deID, "count": row.count} for row in rows]
        }
        
    except Exception as e:
        return {"error": str(e)}






class DepartmentReportResponse(BaseModel):
    serialNo: int
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
    deID: Optional[str] = None
    Com: Optional[str] = None
    departmentName: Optional[str] = None

class DepartmentReportWithTotal(BaseModel):
    records: List[DepartmentReportResponse]
    total: int
    Com: Optional[str] = None
    departmentName: Optional[str] = None



@bookFollowUpRouter.get("/report-with-stats-department", response_model=DepartmentReportWithTotal)
async def get_filtered_department_report(
    bookType: Optional[str] = Query(None, description="Filter by book type"),
    bookStatus: Optional[str] = Query(None, description="Filter by book status"),
    startDate: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    endDate: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    coID: Optional[str] = Query(None, description="Filter by committee ID"),
    deID: Optional[str] = Query(None, description="Filter by department ID"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get filtered book follow-up records by department and committee.
    Returns records with total count and department/committee info.
    Date filtering is applied when both startDate and endDate are provided.
    """
    logger.debug(
        f"Received filtered department report request: "
        f"bookType={bookType}, bookStatus={bookStatus}, "
        f"startDate={startDate}, endDate={endDate}, coID={coID}, deID={deID}"
    )
    return await BookFollowUpService.reportBookFollowUpByDepartment(
        db, bookType, bookStatus, startDate, endDate, coID, deID
    )



# For /committees-with-departments endpoint
class DepartmentInfo(BaseModel):
    deID: str
    departmentName: str

class CommitteeWithDepartmentsResponse(BaseModel):
    coID: str
    Com: str
    departments: List[DepartmentInfo]


# For /report-with-stats-department endpoint  
class DepartmentReportResponse(BaseModel):
    serialNo: int
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
    deID: Optional[str] = None
    Com: Optional[str] = None
    departmentName: Optional[str] = None

class DepartmentReportWithTotal(BaseModel):
    records: List[DepartmentReportResponse]
    total: int
    Com: Optional[str] = None
    departmentName: Optional[str] = None

@bookFollowUpRouter.get("/committees-with-departments", response_model=List[CommitteeWithDepartmentsResponse])
async def get_committees_with_departments(
    bookStatus: Optional[str] = Query(None, description="Filter by book status"),
    startDate: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    endDate: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    coID: Optional[str] = Query(None, description="Filter by specific committee ID"),
    deID: Optional[str] = Query(None, description="Filter by specific department ID"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get all committees that have books with their departments, with optional filtering.
    
    Query Parameters:
        - bookStatus: Filter by book status (e.g., "قيد الانجاز", "منجز")
        - startDate: Start date for date range filter (YYYY-MM-DD)
        - endDate: End date for date range filter (YYYY-MM-DD)
        - coID: Filter by specific committee ID
        - deID: Filter by specific department ID
    
    Returns:
        List of committees with nested department arrays
        
    Examples:
        - Get all: /committees-with-departments
        - Filter by status: /committees-with-departments?bookStatus=قيد الانجاز
        - Filter by dates: /committees-with-departments?startDate=2025-09-01&endDate=2025-09-30
        - Filter by committee: /committees-with-departments?coID=5
        - Combined: /committees-with-departments?bookStatus=قيد الانجاز&startDate=2025-09-01&endDate=2025-09-30&coID=5
    """
    logger.debug(
        f"Fetching committees with departments - "
        f"bookStatus={bookStatus}, startDate={startDate}, endDate={endDate}, "
        f"coID={coID}, deID={deID}"
    )
    return await BookFollowUpService.getAllCommitteesWithDepartments(
        db, bookStatus, startDate, endDate, coID, deID
    )


class DepartmentInfo(BaseModel):
    deID: str
    departmentName: str

class CommitteeDepartmentsResponse(BaseModel):
    coID: str
    Com: str
    departments: List[DepartmentInfo]
    totalDepartments: int


@bookFollowUpRouter.get("/committees/{coID}/departments", response_model=CommitteeDepartmentsResponse)
async def get_departments_by_committee(
    coID: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get all departments for a specific committee that have books.
    
    Args:
        coID: Committee ID
        
    Returns:
        Committee info with its departments array
        
    Example:
        GET /api/bookFollowUp/committees/5/departments
    """
    logger.debug(f"Fetching departments for committee coID={coID}")
    return await BookFollowUpService.getDepartmentsByCommittee(db, coID)