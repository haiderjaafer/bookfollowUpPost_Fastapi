from datetime import datetime
from fastapi import APIRouter, UploadFile, Form, Depends
from sqlalchemy.orm import Session  # ✅ not AsyncSession
from app.database.database import get_db
from app.services.bookFollowUp import BookFollowUpService
from app.services.pdf_service import PDFService
from app.helper.save_pdf import save_pdf_to_server
import os
from app.database.config import settings
from app.models.PDFTable import PDFCreate
from app.models.bookFollowUpTable import BookFollowUpCreate

bookFollowUpRouter = APIRouter(prefix="/api/bookFollowUp", tags=["BookFollowUp"])

@bookFollowUpRouter.post("")
def add_book_with_pdf(
    bookNo: str = Form(...),      # will send data as key-value pairs in form-data with file 
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
    file: UploadFile = Form(...),
    db: Session = Depends(get_db)  
):
    # Insert book
    book_id = BookFollowUpService.insert_book(db, BookFollowUpCreate(
        bookNo=bookNo, bookDate=bookDate, bookType=bookType, directoryName=directoryName,
        incomingNo=incomingNo, incomingDate=incomingDate, subject=subject,
        destination=destination, bookAction=bookAction, bookStatus=bookStatus,
        notes=notes, userID=userID
    ))

    # Count PDFs
    count = PDFService.get_pdf_count(db, book_id)


    # Save file
    upload_dir = settings.PDF_UPLOAD_PATH
    pdf_path = save_pdf_to_server(file.file, bookNo, bookDate, count, upload_dir)


    # Insert PDF record
    PDFService.insert_pdf(db, PDFCreate(
        bookID=book_id,
        bookNo=bookNo,
        countPdf=count,
        pdf=pdf_path,
        userID=userID,
        currentDate=datetime.now().date()  # ✅ Only the date part

    ))


      # ✅ Delete the original file from scanner folder
    try:
        # Save uploaded file temporarily to scanner folder
        scanner_dir = r"D:\booksFollowUp\pdfScanner"
        os.remove(scanner_dir)
    except Exception as e:
        print(f"Warning: Could not delete original file {scanner_dir}. Reason: {e}")


    return {"message": "Book and PDF saved successfully", "bookID": book_id}
