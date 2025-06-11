from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.PDFTable import PDFTable
from app.models.bookFollowUpTable import BookFollowUpResponse, BookFollowUpTable, BookFollowUpCreate
from sqlalchemy import select,func
from fastapi import HTTPException, Request
from app.models.users import Users


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
    async def getAllFilteredBooksNo(
        request: Request,
        db: AsyncSession,
        page: int = 1,
        limit: int = 10,
        bookNo: Optional[str] = None,
        bookStatus: Optional[str] = None,
        bookType: Optional[str] = None,
        directoryName: Optional[str] = None,
        incomingNo: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve all BookFollowUpTable records with pagination, optional filters, and associated PDFs.
        Returns data for DynamicTable with pdfFiles and username for each record.
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
            print(f"Total records: {total}, Page: {page}, Limit: {limit}")

            # Step 2: Pagination offset
            offset = (page - 1) * limit

            # Step 3: Select paginated BookFollowUpTable records with username
            book_stmt = (
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
                    Users.username
                )
                .outerjoin(Users, BookFollowUpTable.userID == Users.id)
                .filter(*filters)
                .distinct(BookFollowUpTable.bookNo)
                .order_by(BookFollowUpTable.bookNo)
                .offset(offset)
                .limit(limit)
            )
            book_result = await db.execute(book_stmt)
            book_rows = book_result.fetchall()

            # Step 4: Fetch PDFs for all bookNos in the current page, including username
            book_nos = [row.bookNo for row in book_rows]
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

            # Step 5: Group PDFs by bookNo
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

            # Step 6: Format data
            data = [
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
                    "bookStatus": row.bookStatus.strip().lower() if row.bookStatus else None,
                    "notes": row.notes,
                    "currentDate": row.currentDate.strftime('%Y-%m-%d') if row.currentDate else None,
                    "userID": row.userID,
                    "username": row.username,  # Add username for book creator
                    "pdfFiles": pdf_map.get(row.bookNo, [])  # PDFs with their usernames
                }
                for row in book_rows
            ]
            print(f"Fetched {len(data)} records with PDFs")

            # Step 7: Response
            return {
                "data": data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit
            }
        except Exception as e:
            print(f"Error fetching books: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")     