from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Date, select, func, cast
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from app.models.architecture.committees import Committee
from app.models.architecture.department import Department
from app.models.bookFollowUpTable import BookFollowUpTable
from app.models.users import Users

import logging

# Configure logger
logger = logging.getLogger(__name__)
if not logger.handlers:  # Avoid duplicate handlers
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


class LateBookFollowUpService:

    @staticmethod
    async def getLateBooks(
        db: AsyncSession,
        page: int = 1,
        limit: int = 10,
        userID: int = None,
    ) -> Dict[str, Any]:
        """
        Retrieve late books (status 'قيد الانجاز') with pagination filtered by userID.
        Returns paginated data with total count, page, limit, total pages, and username.
        """
        try:
            logger.info(f"Getting late books for userID: {userID}, page: {page}, limit: {limit}")
            
            # Validate userID
            if not userID:
                raise HTTPException(status_code=400, detail="userID is required")

            # Base filter conditions
            base_filters = [
                BookFollowUpTable.bookStatus == 'قيد الانجاز',
                BookFollowUpTable.userID == userID  # Apply userID filter to count as well
            ]

            # Step 1: Count total records WITH userID filter applied
            count_stmt = select(func.count(BookFollowUpTable.id)).filter(*base_filters)
            count_result = await db.execute(count_stmt)
            total = count_result.scalar() or 0
            
            logger.info(f"Total late books for userID {userID}: {total}")

            # Step 2: Calculate offset and validate page
            offset = (page - 1) * limit
            total_pages = (total + limit - 1) // limit if total > 0 else 1
            
            # Validate page number
            if page > total_pages and total > 0:
                logger.warning(f"Page {page} exceeds total pages {total_pages}")
                return {
                    "data": [],
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "totalPages": total_pages
                }

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
            ).outerjoin(
                Users, BookFollowUpTable.userID == Users.id
            ).outerjoin(
                Department, BookFollowUpTable.deID == Department.deID
            ).outerjoin(
                Committee, Department.coID == Committee.coID
            ).filter(
                *base_filters  # Apply same filters as count query
            ).order_by(
                BookFollowUpTable.currentDate.desc()
            ).offset(offset).limit(limit)

            # Execute query
            result = await db.execute(query)
            late_books = result.fetchall()

            logger.info(f"Retrieved {len(late_books)} records for page {page}")

            # Step 4: Format response
            data = [
                {   
                    "serialNo": offset + i + 1,  # Auto-increment serial number based on pagination
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
                    "currentDate": book.currentDate.strftime('%Y-%m-%d') if book.currentDate else None,
                    "userID": book.userID,
                    "username": book.username,
                    "deID": book.deID,
                    "Com": book.Com,
                    "departmentName": book.departmentName,
                    "pdfFiles": []  # Empty array to match BookFollowUpData
                }
                for i, book in enumerate(late_books)
            ]

            # Step 5: Response with proper pagination info
            response = {
                "data": data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": total_pages
            }
            
            logger.info(f"Response: {len(data)} records, Total: {total}, Page: {page}/{total_pages}")
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching late books: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")