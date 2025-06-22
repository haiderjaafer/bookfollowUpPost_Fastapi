import os
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_async_db
from app.models.users import UserCreate
from app.services.authentication import AuthenticationService
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Authenticate user and set JWT cookie.
    
    Args:
        request: LoginRequest with username and password
        response: FastAPI Response to set cookie
        db: AsyncSession dependency
        
    Returns:
        JSON response with message
    """
    try:
        # Verify user credentials
        user = await AuthenticationService.verify_user(db, request.username, request.password)
        
        # Generate JWT
        token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="jwtToken",
            value=token,
            httponly=True,
            secure=os.getenv("NODE_ENV") == "production",
            samesite="strict",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/"
        )
        
        return {"message": "Authenticated"}
        
    except HTTPException as e:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
    



@router.post("/register")
async def register(
    user_create: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Register a new user.
    """
    try:
        user = await AuthenticationService.create_user(db, user_create)

        token = AuthenticationService.generate_jwt(
        user_id=user.id,
        username=user.username,
        permission=user.permission
            )
        
        # Set HTTP-only cookie
        response.set_cookie(
            key="jwtToken",
            value=token,
            httponly=True,
            secure=os.getenv("NODE_ENV") == "production",
            samesite="strict",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/"
        )


        return {"message": F"Authenticated{user}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")