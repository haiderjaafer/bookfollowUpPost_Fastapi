from datetime import datetime
from fastapi import APIRouter, UploadFile, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession  # ✅ Use AsyncSession instead of sync Session
from app.database.database import get_async_db  # ✅ Import async DB dependency
from app.services.bookFollowUp import BookFollowUpService
from app.services.pdf_service import PDFService
from app.helper.save_pdf import save_pdf_to_server  # ✅ Responsible for saving the uploaded file
import os
from app.database.config import settings
from app.models.PDFTable import PDFCreate
from app.models.bookFollowUpTable import BookFollowUpCreate

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
