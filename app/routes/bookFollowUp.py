from datetime import datetime,timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, Form, Depends
import pydantic
from sqlalchemy import select,extract,func
from sqlalchemy.ext.asyncio import AsyncSession  # ✅ Use AsyncSession instead of sync Session
from app.database.database import get_async_db  # ✅ Import async DB dependency
from app.services.bookFollowUp import BookFollowUpService
from app.services.pdf_service import PDFService
from app.helper.save_pdf import save_pdf_to_server  # ✅ Responsible for saving the uploaded file
import os
from app.database.config import settings
from app.models.PDFTable import PDFCreate
from app.models.bookFollowUpTable import BookFollowUpCreate, BookFollowUpResponse, BookFollowUpTable, PaginatedOrderOut
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Date


# ✅ Create router with a prefix and tag for grouping endpoints
bookFollowUpRouter = APIRouter(prefix="/api/bookFollowUp", tags=["BookFollowUp"])

# ✅ POST endpoint to add a book and upload a related PDF file
@bookFollowUpRouter.post("")
async def add_book_with_pdf(
    # ✅ Receive form data fields
    bookNo: str = Form(...),
    bookDate: str = Form(...),
    bookType: str = Form(...),
    directoryName: str = Form(...),
    incomingNo: str = Form(...),
    incomingDate: str = Form(...),
    subject: str = Form(...),
    destination: str = Form(...),
    bookAction: str = Form(...),
    bookStatus: str = Form(...),
    notes: str = Form(...),
    userID: str = Form(...),
    file: UploadFile = Form(...),  # ✅ File is sent in multipart form
    db: AsyncSession = Depends(get_async_db)  # ✅ Use Async DB session
):
    # ✅ Insert book record into DB using BookFollowUpService
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
        currentDate=datetime.now().date(),
        userID=userID
    )
    book_id = await BookFollowUpService.insert_book(db, book_data)

    # ✅ Count how many PDFs are already associated with this book
    count = await PDFService.get_pdf_count(db, book_id)

    # ✅ Save uploaded file to the destination path and return the new path
    upload_dir = settings.PDF_UPLOAD_PATH
    pdf_path = save_pdf_to_server(file.file, bookNo, bookDate, count, upload_dir)

    # ✅ Create a new PDF record to store in the PDFTable
    pdf_data = PDFCreate(
        bookID=book_id,
        bookNo=bookNo,
        countPdf=count,
        pdf=pdf_path,
        userID=int(userID),  # ✅ Ensure this is an integer
        currentDate=datetime.now().date()  # ✅ Convert datetime to date only
    )
    await PDFService.insert_pdf(db, pdf_data)

    # ✅ Attempt to delete the original uploaded file from scanner folder
    try:
        # This assumes the file has been saved temporarily at the path below
        scanner_path = os.path.join(settings.PDF_SOURCE_PATH, file.filename)
        os.remove(scanner_path)
    except Exception as e:
        print(f"⚠️ Warning: Could not delete original file {scanner_path}. Reason: {e}")

    # ✅ Return success response with inserted book ID
    return {"message": "Book and PDF saved successfully", "bookID": book_id}




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



@bookFollowUpRouter.get("/getAll", response_model=PaginatedOrderOut)
async def get_BookFollowUp(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    bookNo : Optional[str] = Query(None),
    bookStatus: Optional[str] = Query(None, enum=["منجز", "قيد الانجاز","مداولة"]),
    bookType: Optional[str] = Query(None),
    directoryName: Optional[str] = Query(None),
    incomingNo: Optional[str] = Query(None)
):
    return await BookFollowUpService.getAllorderNo(
        request=request,
        db=db,
        page=page,
        limit=limit,
        bookNo= bookNo,
        bookStatus=bookStatus,
        bookType=bookType,
        directoryName=directoryName,
        incomingNo=incomingNo
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




class LateBookResponse(pydantic.BaseModel):
    id: int
    bookType: str | None
    bookNo: str | None
    bookDate: str | None
    directoryName: str | None
    incomingNo: str | None
    incomingDate: str | None
    subject: str | None
    destination: str | None
    bookAction: str | None
    bookStatus: str | None
    notes: str | None
    countOfLateBooks: int
    currentDate: str | None
    userID: int | None

    class Config:
        from_attributes = True

@bookFollowUpRouter.get("/lateBooks", response_model=Dict[str, Any])
async def get_late_books(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(10, ge=1, le=100, description="Records per page"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Retrieve late books (status 'قيد الانجاز', incomingDate within last 5 days) with pagination.
    Returns paginated data with total count, page, limit, and total pages.
    """
    try:
        # Get current date in +03:00 timezone
        tz = timezone(timedelta(hours=3))  # +03:00 offset
        current_date = datetime.now(tz).date()
        start_date = current_date - timedelta(days=5)

        # Step 1: Count total records
        count_stmt = select(func.count()).select_from(
            select(BookFollowUpTable.id).filter(
                BookFollowUpTable.bookStatus == 'قيد الانجاز',
                cast(BookFollowUpTable.incomingDate, Date) >= start_date,
                cast(BookFollowUpTable.incomingDate, Date) <= current_date
            ).subquery()
        )
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Step 2: Calculate offset
        offset = (page - 1) * limit

        # Step 3: Build query for paginated data
        query = select(
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
            BookFollowUpTable.userID
        ).filter(
            BookFollowUpTable.bookStatus == 'قيد الانجاز',
            cast(BookFollowUpTable.incomingDate, Date) >= start_date,
            cast(BookFollowUpTable.incomingDate, Date) <= current_date
        ).order_by(
            BookFollowUpTable.incomingDate.asc()
        ).offset(offset).limit(limit)

        # Execute query
        result = await db.execute(query)
        late_books = result.fetchall()

        # Step 4: Format response and calculate days late
        data = [
            {
                "id": book.id,
                "bookType": book.bookType,
                "bookNo": book.bookNo,
                "bookDate": book.bookDate.strftime('%Y-%m-%d') if book.bookDate else None,
                "directoryName": book.directoryName,
                "incomingNo": book.incomingNo,
                "incomingDate": book.incomingDate.strftime('%Y-%m-%d') if book.incomingDate else None,
                "subject": book.subject,
                "destination": book.destination,
                "bookAction": book.bookAction,
                "bookStatus": book.bookStatus,
                "notes": book.notes,
                "countOfLateBooks": (current_date - book.incomingDate).days if book.incomingDate else 0,
                "currentDate": book.currentDate.strftime('%Y-%m-%d') if book.currentDate else None,
                "userID": book.userID
            }
            for book in late_books
        ]

        # Step 5: Response
        print(f"Fetched {len(data)} late books, Total: {total}, Page: {page}, Limit: {limit}")  # Debug
        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": (total + limit - 1) // limit
        }
    except Exception as e:
        print(f"Error fetching late books: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")