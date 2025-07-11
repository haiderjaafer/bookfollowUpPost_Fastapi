import os  # For path operations like join, exists
import shutil  # For copying file-like objects efficiently
from datetime import datetime  # For getting current timestamp
from typing import BinaryIO  # Type hint for file-like object
from pathlib import Path
import threading
import asyncio

def save_pdf_to_server(source_file: BinaryIO, book_no: str, book_date: str, count: int, dest_dir: str) -> str:
    #  Get current datetime to include in filename
    now = datetime.now()

    #  Extract year from book_date (format must be YYYY-MM-DD)
    year = datetime.strptime(book_date, "%Y-%m-%d").year

    #  Format a timestamp to ensure unique filenames
    timestamp = now.strftime("%Y-%m-%d_%I-%M-%S-%p")  # Example: 2025-05-27_11-30-15-AM

    #  Construct unique filename: bookNo.year.count+1-timestamp.pdf
    filename = f"{book_no}.{year}.{count + 1}-{timestamp}.pdf"

    dest_path = Path(dest_dir) / filename  # pathlib auto-handles separators correctly

    print(f"dest_path....{dest_path}")

    #  Check if the file already exists (to avoid overwriting)
    if dest_path.exists():
        raise FileExistsError("PDF already exists.")

    #  Write the uploaded file to the destination path
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(source_file, buffer)  # Efficiently copy from uploaded file to destination

    #  Return the final saved file path (used in DB)
    return str(dest_path)  # Return string path




async def async_delayed_delete(file_path: str, delay_sec: int = 3):
    await asyncio.sleep(delay_sec)
    try:
        os.remove(file_path)
        print(f"✅ Async deleted: {file_path}")
    except Exception as e:
        print(f"⚠️ Async deletion failed: {e}")




# use threading to delete pdf file 
# def delayed_delete(file_path: str, delay_sec: int = 3):          #common Python pattern called a nested function or closure 
#     def try_delete():
#         try:
#             os.remove(file_path)
#             print(f"Delayed deletion success: {file_path}")
#         except Exception as e:
#             print(f"⚠️ Delayed deletion failed: {e}")
#     threading.Timer(delay_sec, try_delete).start()              #You don’t have to stop or clean anything manually — Python’s thread system handles it

