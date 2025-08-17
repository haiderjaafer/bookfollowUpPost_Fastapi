from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Date, select, func, cast
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from app.models.architecture.committees import Committee
from app.models.architecture.department import Department
from app.models.bookFollowUpTable import BookFollowUpTable
from app.models.users import Users

class LateBookFollowUpService:

    @staticmethod
    async def getLateBooks(
        db: AsyncSession,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve late books (status 'قيد الانجاز', incomingDate within last 5 days) with pagination.
        Returns paginated data with total count, page, limit, total pages, and username.
        """
        try:
            # Get current date in +03:00 timezone
            tz = timezone(timedelta(hours=3))
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

            # Step 3: Build query for paginated data with username
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
                BookFollowUpTable.userID,
                Users.username,
                BookFollowUpTable.deID,
                Department.departmentName,
                Committee.Com
            ).outerjoin( Users, BookFollowUpTable.userID == Users.id ).outerjoin(Department, BookFollowUpTable.deID == Department.deID).outerjoin(Committee, Department.coID == Committee.coID).filter(
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
                    # "destination": book.destination,
                    "bookAction": book.bookAction,
                    "bookStatus": book.bookStatus,
                    "notes": book.notes,
                    "countOfLateBooks": (current_date - book.incomingDate).days if book.incomingDate else 0,
                    "currentDate": book.currentDate.strftime('%Y-%m-%d') if book.currentDate else None,
                    "userID": book.userID,
                    "username": book.username,
                    "deID": book.deID,
                    "Com": book.Com,
                    "departmentName": book.departmentName,
                    "pdfFiles": []  # Empty array to match BookFollowUpData
                }
                for book in late_books
            ]

            # Step 5: Response
            print(f"Fetched {len(data)} late books, Total: {total}, Page: {page}, Limit: {limit}")
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