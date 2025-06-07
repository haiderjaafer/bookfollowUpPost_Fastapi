from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.bookFollowUpTable import BookFollowUpResponse, BookFollowUpTable, BookFollowUpCreate
from sqlalchemy import select,func
from fastapi import Request


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
    

    #http://127.0.0.1:9000/api/bookFollowUp/getAllDirectoryNames?search=مكتب
    #http://127.0.0.1:9000/api/bookFollowUp/getAllIncomingNo
    #http://127.0.0.1:9000/api/bookFollowUp/getAllBooksNo


  


    @staticmethod
    async def getAllorderNo(
        request: Request,
        db: AsyncSession,
        page: int = 1,
        limit: int = 10,
        bookNo: Optional[str] = None,
        bookStatus: Optional[str] = None,
        bookType: Optional[str] = None,
        directoryName: Optional[str] = None,
        incomingNo: Optional[str] = None,
        
    ):
        # Optional filters
        filters = []

        # Remove empty query parameter logic or make it optional
        # Commenting out to allow empty strings as "no filter"
        """
        query_params = request.query_params
        for param in ["bookType", "directoryName", "incomingNo"]:
            if param in query_params and not query_params[param].strip():
                return {
                    "data": [],
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "totalPages": 0
                }
        """

        # Add filters if provided
        if bookNo:
            filters.append(BookFollowUpTable.bookNo == bookNo.strip())
        if bookStatus:
            filters.append(BookFollowUpTable.bookStatus == bookStatus.strip().lower())
        if bookType:
            filters.append(BookFollowUpTable.bookType == bookType.strip())
        if directoryName:
            filters.append(BookFollowUpTable.directoryName == directoryName.strip())
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
        total = count_result.scalar()
        print(f"Total: {total}, Limit: {limit}, TotalPages: {(total + limit - 1) // limit}")  # Debug

        # Step 2: Pagination offset
        offset = (page - 1) * limit

        # Step 3: Select paginated records
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
            )
            .filter(*filters)
            .distinct(BookFollowUpTable.bookNo)
            .order_by(BookFollowUpTable.bookNo)
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        # Step 4: Format data and normalize bookStatus
        data = [
            {
                "id": row.id,
                "bookType": row.bookType,
                "bookNo": row.bookNo,
                "bookDate": row.bookDate,
                "directoryName": row.directoryName,
                "incomingNo": row.incomingNo,
                "incomingDate": row.incomingDate,
                "subject": row.subject,
                "destination": row.destination,
                "bookAction": row.bookAction,
                "bookStatus": row.bookStatus.strip().lower() if row.bookStatus else None,  # Normalize
                "notes": row.notes,
                "currentDate": row.currentDate,
                "userID": row.userID,
            }
            for row in rows
        ]
        print("BookStatus values:", [row["bookStatus"] for row in data])  # Debug

        # Step 5: Response
        return {
            "data": data,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": (total + limit - 1) // limit
        }