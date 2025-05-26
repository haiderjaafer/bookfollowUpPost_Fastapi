from typing import List, Optional
from fastapi import  APIRouter, Depends, HTTPException, status, Request ,Query
from sqlalchemy.orm import Session  
from app.models.bookFollowUpTable import BookFollowUpTable,BookFollowUpCreate,BookFollowUpResponse
from app.database.database import get_db
from app.services.bookFollowUp import BookFollowUpClass



# ================= API Routes =================
bookFollowUpRouter = APIRouter(prefix="/api/bookFollowUp", tags=["BookFollowUp"])


@bookFollowUpRouter.post("/bookfollowUpPost")
def insert_book_follow_up(data: BookFollowUpCreate, db: Session = Depends(get_db)):
    try:
        record = BookFollowUpClass.create_book_follow_up(db, data)
        return {"status": "success", "data": record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





