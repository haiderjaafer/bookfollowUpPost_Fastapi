from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Date, select, func, cast
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from app.models.architecture.committees import Committee
from app.models.architecture.department import Department
from app.models.bookFollowUpTable import BookFollowUpTable, BookJunctionBridge, CommitteeDepartmentsJunction
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
        Updated for new multi-department schema with junctions and bridges.
        """
        try:
            logger.info(f"Getting late books for userID: {userID}, page: {page}, limit: {limit}")
            
            # Validate userID
            if not userID:
                raise HTTPException(status_code=400, detail="userID is required")

            # Base filter conditions
            base_filters = [
                BookFollowUpTable.bookStatus == 'قيد الانجاز',
                BookFollowUpTable.userID == userID
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

            # Step 3: Build query for paginated data with primary junction info
            query = select(
                BookFollowUpTable.id,
                BookFollowUpTable.bookType,
                BookFollowUpTable.bookNo,
                BookFollowUpTable.bookDate,
                BookFollowUpTable.directoryName,
                BookFollowUpTable.junctionID,  # Include junctionID
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
                # Get primary department and committee from junction
                Department.deID,
                Department.departmentName,
                Committee.coID,
                Committee.Com
            ).outerjoin(
                Users, BookFollowUpTable.userID == Users.id
            ).outerjoin(
                # Join through junctionID instead of direct deID
                CommitteeDepartmentsJunction, 
                BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
            ).outerjoin(
                Department, CommitteeDepartmentsJunction.deID == Department.deID
            ).outerjoin(
                Committee, CommitteeDepartmentsJunction.coID == Committee.coID
            ).filter(
                *base_filters
            ).order_by(
                BookFollowUpTable.currentDate.desc()
            ).offset(offset).limit(limit)

            # Execute main query
            result = await db.execute(query)
            late_books = result.fetchall()

            # Step 4: Get ALL departments for each book (optional - for complete multi-department view)
            book_ids = [book.id for book in late_books]
            dept_map = {}
            
            if book_ids:
                # Query to get all departments for each late book
                all_departments_stmt = (
                    select(
                        BookFollowUpTable.id.label('book_id'),
                        Department.deID,
                        Department.departmentName,
                        Committee.coID,
                        Committee.Com
                    )
                    .select_from(BookFollowUpTable)
                    .join(BookJunctionBridge, BookFollowUpTable.id == BookJunctionBridge.bookID)
                    .join(CommitteeDepartmentsJunction, BookJunctionBridge.junctionID == CommitteeDepartmentsJunction.id)
                    .join(Committee, CommitteeDepartmentsJunction.coID == Committee.coID)
                    .join(Department, CommitteeDepartmentsJunction.deID == Department.deID)
                    .filter(BookFollowUpTable.id.in_(book_ids))
                    .order_by(BookFollowUpTable.id, Department.departmentName)
                )
                
                dept_result = await db.execute(all_departments_stmt)
                dept_rows = dept_result.fetchall()
                
                # Group departments by book_id
                for dept in dept_rows:
                    if dept.book_id not in dept_map:
                        dept_map[dept.book_id] = []
                    dept_map[dept.book_id].append({
                        "deID": dept.deID,
                        "departmentName": dept.departmentName,
                        "coID": dept.coID,
                        "Com": dept.Com
                    })

            logger.info(f"Retrieved {len(late_books)} records for page {page}")

            # Step 5: Format response
            data = []
            for i, book in enumerate(late_books):
                all_departments = dept_map.get(book.id, [])
                dept_names = [dept["departmentName"] for dept in all_departments if dept["departmentName"]]
                
                data.append({   
                    "serialNo": offset + i + 1,
                    "id": book.id,
                    "bookType": book.bookType,
                    "bookNo": book.bookNo,
                    "bookDate": book.bookDate.strftime('%Y-%m-%d') if book.bookDate else None,
                    "directoryName": book.directoryName,
                    "junctionID": book.junctionID,  # Include junction ID
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
                    
                    # Primary department info (from junctionID)
                    "deID": book.deID,
                    "departmentName": book.departmentName,
                    "coID": book.coID,
                    "Com": book.Com,
                    
                    # All departments for this book
                    "all_departments": all_departments,
                    "department_names": ", ".join(dept_names),
                    "department_count": len(all_departments),
                    
                    "pdfFiles": []  # Empty array to match BookFollowUpData
                })

            # Step 6: Response with proper pagination info
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



    # # Alternative simplified version if you only need primary department
    # @staticmethod
    # async def getLateBooksSimple(
    #     db: AsyncSession,
    #     page: int = 1,
    #     limit: int = 10,
    #     userID: int = None,
    # ) -> Dict[str, Any]:
    #     """
    #     Simplified version that only shows primary department from junctionID
    #     """
    #     try:
    #         logger.info(f"Getting late books (simple) for userID: {userID}, page: {page}, limit: {limit}")
            
    #         if not userID:
    #             raise HTTPException(status_code=400, detail="userID is required")

    #         base_filters = [
    #             BookFollowUpTable.bookStatus == 'قيد الانجاز',
    #             BookFollowUpTable.userID == userID
    #         ]

    #         # Count query
    #         count_stmt = select(func.count(BookFollowUpTable.id)).filter(*base_filters)
    #         count_result = await db.execute(count_stmt)
    #         total = count_result.scalar() or 0

    #         # Pagination
    #         offset = (page - 1) * limit
    #         total_pages = (total + limit - 1) // limit if total > 0 else 1

    #         # Main query - only primary department
    #         query = select(
    #             BookFollowUpTable.id,
    #             BookFollowUpTable.bookType,
    #             BookFollowUpTable.bookNo,
    #             BookFollowUpTable.bookDate,
    #             BookFollowUpTable.directoryName,
    #             BookFollowUpTable.junctionID,
    #             BookFollowUpTable.incomingNo,
    #             BookFollowUpTable.incomingDate,
    #             BookFollowUpTable.subject,
    #             BookFollowUpTable.destination,
    #             BookFollowUpTable.bookAction,
    #             BookFollowUpTable.bookStatus,
    #             BookFollowUpTable.notes,
    #             BookFollowUpTable.currentDate,
    #             BookFollowUpTable.userID,
    #             Users.username,
    #             Department.deID,
    #             Department.departmentName,
    #             Committee.coID,
    #             Committee.Com
    #         ).outerjoin(
    #             Users, BookFollowUpTable.userID == Users.id
    #         ).outerjoin(
    #             CommitteeDepartmentsJunction, 
    #             BookFollowUpTable.junctionID == CommitteeDepartmentsJunction.id
    #         ).outerjoin(
    #             Department, CommitteeDepartmentsJunction.deID == Department.deID
    #         ).outerjoin(
    #             Committee, CommitteeDepartmentsJunction.coID == Committee.coID
    #         ).filter(
    #             *base_filters
    #         ).order_by(
    #             BookFollowUpTable.currentDate.desc()
    #         ).offset(offset).limit(limit)

    #         result = await db.execute(query)
    #         late_books = result.fetchall()

    #         # Format response - simplified
    #         data = [
    #             {   
    #                 "serialNo": offset + i + 1,
    #                 "id": book.id,
    #                 "bookType": book.bookType,
    #                 "bookNo": book.bookNo,
    #                 "bookDate": book.bookDate.strftime('%Y-%m-%d') if book.bookDate else None,
    #                 "directoryName": book.directoryName,
    #                 "junctionID": book.junctionID,
    #                 "incomingNo": book.incomingNo,
    #                 "incomingDate": book.incomingDate.strftime('%Y-%m-%d') if book.incomingDate else None,
    #                 "subject": book.subject,
    #                 "destination": book.destination,
    #                 "bookAction": book.bookAction,
    #                 "bookStatus": book.bookStatus,
    #                 "notes": book.notes,
    #                 "currentDate": book.currentDate.strftime('%Y-%m-%d') if book.currentDate else None,
    #                 "userID": book.userID,
    #                 "username": book.username,
    #                 "deID": book.deID,
    #                 "departmentName": book.departmentName,
    #                 "coID": book.coID,
    #                 "Com": book.Com,
    #                 "pdfFiles": []
    #             }
    #             for i, book in enumerate(late_books)
    #         ]

    #         return {
    #             "data": data,
    #             "total": total,
    #             "page": page,
    #             "limit": limit,
    #             "totalPages": total_pages
    #         }
            
    #     except Exception as e:
    #         logger.error(f"Error fetching late books (simple): {str(e)}", exc_info=True)
    #         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    

