import os
from fastapi import APIRouter, Depends, HTTPException, Response,Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_async_db
from app.models.users import UserCreate
from app.services.authentication import AuthenticationService
from pydantic import BaseModel
from typing import Optional
from app.database.config import settings
import logging
from pathlib import Path
from app.database.config import settings


# Updated login route with proper cookie configuration
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
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
        print(f"auth...{request.username, request.password}")
        # Verify user credentials
        user = await AuthenticationService.verify_user(db, request.username, request.password)

        print(f"user .login,,,,,.. {user.permission}")           
        # # Generate JWT
        token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )

        print(f"token ... {token}")  
        
   

        response.set_cookie(
            key="jwt_cookies_auth_token",
            value=token,
            httponly=True,           # Prevent JS access
            secure=os.getenv("NODE_ENV") == "production",            # False for localhost HTTP
            samesite="lax",          # Lax for cross-origin in development
            max_age=60 * 60 * 24 * 30 ,    # 30 days
            path="/",                # Available site-wide
            # 🔥 DO NOT set domain for localhost
            # domain="127.0.0.1"
        )



        
    
        
        return {"message": "Login successful", "user": {"id": user.id, "username": user.username,"permission":user.permission}}
       
        
             
    except HTTPException as e:
        logger.warning(f"Authentication failed for user {request.username}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")





@router.post("/register")
async def register(
    user_create: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Register a new user and create their personal directory if it does not exist.
    """
    try:
        # 1. Create user in DB
        user = await AuthenticationService.create_user(db, user_create)

        # 2. Build user directory path
        base_dir = Path(settings.PDF_SOURCE_PATH)
        # print("base_dir", base_dir)
        if not base_dir:
            raise HTTPException(status_code=500, detail="PDF_SOURCE_PATH not configured.")

        # user_dir = os.path.join(settings.PDF_SOURCE_PATH,  user.username)
        user_dir = base_dir / f"{user.username}"
        print("base_dir", user_dir)
        if user_dir.exists():
            print(f"Directory already exists for user {user.username}: {user_dir}")
        else:
            try:
                user_dir.mkdir(parents=True, exist_ok=False)
                print(f"Created directory for user {user.username}: {user_dir}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to create directory: {str(e)}")

        # 3. Issue JWT token
        token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )

        # 4. Set JWT cookie
        response.set_cookie(
            key="jwt_cookies_auth_token",
            value=token,
            httponly=True,
            secure=settings.NODE_ENV == "production",
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/"
        )

        return {
            "success": True,
            "message": f"User {user.username} registered successfully",
            "directory": str(user_dir),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")  








@router.post("/logout")
async def logout(response: Response):
    """
    Log out by clearing the jwtToken cookie.
    """
    print("logout....")

    response.delete_cookie(
        key="jwt_cookies_auth_token",    
        # httponly=True,           
        # secure=False,            
        # samesite="lax",             
        path="/",
    )
    return {"message": "Logged out successfully"}





    