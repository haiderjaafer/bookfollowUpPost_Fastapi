import os
import shutil
from datetime import datetime
from typing import BinaryIO

def save_pdf_to_server(source_file: BinaryIO, book_no: str, book_date: str, count: int, dest_dir: str) -> str:
    now = datetime.now()
    year = datetime.strptime(book_date, "%Y-%m-%d").year
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{book_no}.{year}.{count + 1}-{timestamp}.pdf"
    destination = os.path.join(dest_dir, filename)

    if os.path.exists(destination):
        raise FileExistsError("PDF already exists.")

    # Save the file using copyfileobj
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(source_file, buffer)

    return destination
