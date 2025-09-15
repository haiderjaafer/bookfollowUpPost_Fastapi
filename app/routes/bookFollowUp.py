import asyncio
from datetime import datetime,timedelta, timezone
from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Form, Depends
import pydantic
from sqlalchemy import select,extract,func
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
from app.models.bookFollowUpTable import BookFollowUpCreate, BookFollowUpResponse, BookFollowUpTable, BookFollowUpWithPDFResponseForUpdateByBookID, BookStatusCounts, BookTypeCounts, PaginatedOrderOut, UserBookCount
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date
from app.services.lateBooks import LateBookFollowUpService
from fastapi.responses import FileResponse
import os
from urllib.parse import unquote
import logging

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:  # Avoid duplicate handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

#  Create router with a prefix and tag for grouping endpoints
bookFollowUpRouter = APIRouter(prefix="/api/bookFollowUp", tags=["BookFollowUp"])



@bookFollowUpRouter.post("")
async def add_book_with_pdf(
    bookNo: str = Form(...),
    bookDate: str = Form(...),
    bookType: str = Form(...),
    directoryName: str = Form(...),
    deID: str = Form(...),
    incomingNo: str = Form(...),
    incomingDate: str = Form(...),
    subject: str = Form(...),
    # destination: str = Form(...),
    bookAction: str = Form(...),
    bookStatus: str = Form(...),
    notes: str = Form(...),
    userID: str = Form(...),
    file: UploadFile = Form(...),
    username: str = Form(),
    db: AsyncSession = Depends(get_async_db)
    
):
    try:
        # Insert book
        book_data = BookFollowUpCreate(
            bookNo=bookNo,
            bookDate=bookDate,
            bookType=bookType,
            directoryName=directoryName,
            deID=deID,
            incomingNo=incomingNo,
            incomingDate=incomingDate,
            subject=subject,
            destination="destination",
            bookAction=bookAction,
            bookStatus=bookStatus,
            notes=notes,
            currentDate=datetime.today().strftime('%Y-%m-%d'),
            userID=userID
        )
        book_id = await BookFollowUpService.insert_book(db, book_data)
        print(f"Inserted book with ID: {book_id}")

        # Count PDFs
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
            userID=int(userID),
            currentDate=datetime.now().date().isoformat()
        )
        await PDFService.insert_pdf(db, pdf_data)
        print(f"Inserted PDF record: {pdf_path}")

        # Delete original file (with delay)
        scanner_path = os.path.join(settings.PDF_SOURCE_PATH,username, file.filename)
        print(f"Attempting to delete: {scanner_path}")
        if os.path.isfile(scanner_path):                                          # os.path.isfile(...) to ensure the file exists
           # delayed_delete(scanner_path, delay_sec=3)
           asyncio.create_task(async_delayed_delete(scanner_path, delay_sec=3))   #asyncio.create_task(...) to run async_delayed_delete(...) in the background  and No await, so it doesn’t block the request 

        else:
            print(f" File not found for deletion: {scanner_path}")

        return {"message": "Book and PDF saved successfully", "bookID": book_id}

    except Exception as e:
        print(f"❌ Error in add_book_with_pdf: {str(e)}")
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
    Retrieve late books (status 'قيد الانجاز', incomingDate within last 5 days) with pagination.
    Returns paginated data with total count, page, limit, and total pages.
    """
    return await LateBookFollowUpService.getLateBooks(db, page, limit,userID)




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
    userID: Optional[str] = Form(None),  # FIXED: Removed space in "userI  D"
    username: Optional[str] = Form(None),  # FIXED: Changed from Form() to Form(None)
    selectedCommittee: Optional[str] = Form(None),  # Added missing field
    deID: Optional[str] = Form(None),  # Added missing field
    file: Optional[UploadFile] = File(None),  # FIXED: Changed from Form(None) to File(None)
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update a book record by ID with provided fields and optionally add a new PDF.
    Args:
        id: Path parameter for the book ID.
        bookNo, bookDate, ...: Optional form fields to update.
        userID: Optional user ID for book and PDF.
        file: Optional PDF file to add.
        db: Async SQLAlchemy session.
    Returns:
        JSON response with success message and updated book ID.
    Raises:
        HTTPException: For validation errors, missing book, or server errors.
    """
    try:
        logger.info(f"Updating book ID {id} with data: bookNo={bookNo}, userID={userID}, file={file.filename if file else None}")
        
        # Validate at least one field or file is provided
        form_fields = [
            bookNo, bookDate, bookType, directoryName, incomingNo,
            incomingDate, subject, destination, bookAction, bookStatus,
            notes, userID, selectedCommittee, deID
        ]
        
        # Check if we have a valid file
        has_file = file is not None and hasattr(file, 'filename') and file.filename
        
        # Check if we have at least one form field with a value
        has_form_data = any(v is not None and str(v).strip() != '' for v in form_fields)
        
        if not has_form_data and not has_file:
            raise HTTPException(status_code=400, detail="At least one field or file must be provided")

        # Create book data model
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
            userID=int(userID) if userID else None,
            selectedCommittee=int(selectedCommittee) if selectedCommittee else None,
            deID=int(deID) if deID else None
        )

        logger.debug(f"Book data created: {book_data}")

        # Call service method
        updated_book_id = await BookFollowUpService.update_book(
            db,
            id,
            book_data,
            file if has_file else None,  # Only pass file if it's valid
            int(userID) if userID else None,
            username
        )

        return {
            "message": "Book updated successfully",
            "bookID": updated_book_id
        }

    except ValueError as e:
        logger.error(f"Invalid input for ID {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_book_with_pdf for ID {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# Alternative approach: Create a separate route for JSON updates
@bookFollowUpRouter.patch("/{id}/json", response_model=Dict[str, Any])
async def update_book_json(
    id: int,
    book_data: BookFollowUpCreate,  # Use a Pydantic model for JSON
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update a book record by ID using JSON data (no file upload).
    """
    try:
        logger.info(f"JSON update for book ID {id}: {book_data}")
        
        # Convert to BookFollowUpCreate
        create_data = BookFollowUpCreate(**book_data.model_dump(exclude_none=True))
        
        # Call service method without file
        updated_book_id = await BookFollowUpService.update_book(
            db,
            id,
            create_data,
            file=None,
            user_id=book_data.userID,
            username=None
        )

        return {
            "message": "Book updated successfully",
            "bookID": updated_book_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in JSON update for ID {id}: {str(e)}")
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
    Fetch a book by ID with all fields, associated PDFs, PDF count, and username.
    Args:
        id: Book ID to fetch.
        db: Async SQLAlchemy session.
    Returns:
        BookFollowUpWithPDFResponseForUpdateByBookID with book data, PDFs, and username.
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
    Get filtered book follow-up report. If check=True, filter by date range.
    If check=False, filter by currentDate IS NULL.

    Args:
        bookType: Filter by book type
        bookStatus: Filter by book status
        check: Enable date range filtering (True) or NULL currentDate (False)
        startDate: Start date for filtering (YYYY-MM-DD)
        endDate: End date for filtering (YYYY-MM-DD)
        db: AsyncSession dependency
    
    Returns:
        List of book follow-up records
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
    



@bookFollowUpRouter.get("/getRecordBySubject", response_model=Dict[str, Any])
async def getRecordBySubjectFunction(
    request: Request,
    subject: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    if subject:
        decoded_subject = unquote(subject)
    #     print(f" subject .......... {decoded_subject}")
    #     return decoded_subject
    # return "No subject provided"

    logger.info(f"Received request for subject: {subject}")
    return await BookFollowUpService.getRecordBySubject(db, subject)
