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


# Updated login route with proper cookie configuration
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database.config import settings
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

        print(f"user ... {user}")           
        # # Generate JWT
        token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )

        print(f"token ... {token}")  
        
        # 🔥 CRITICAL: Cookie settings for browser compatibility
        response.set_cookie(
            key="app_jwt_token_auth",
            value=token,
            httponly=True,           # Prevent JS access
            secure=os.getenv("NODE_ENV") == "production",            # False for localhost HTTP
            samesite="lax",          # Lax for cross-origin in development
            max_age=60 * 60 * 24 * 30 ,    # 30 days
            path="/",                # Available site-wide
            # 🔥 DO NOT set domain for localhost
            # domain="127.0.0.1"
        )
        
        # Add explicit headers for debugging
        # response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # logger.info(f"Login successful for user: {user.username}")
        # logger.debug(f"Cookie set: jwtToken (length: {len(token)})")
        
        return {"message": "Login successful", "user": {"id": user.id, "username": user.username}}
        
             
    except HTTPException as e:
        logger.warning(f"Authentication failed for user {request.username}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



# @router.get("/test-cookie")
# async def test_cookie(response: Response):
#     """Test endpoint to verify cookie setting works"""
#     response.set_cookie(
#         key="testCookie",
#         value="test123",
#         httponly=False,  # Allow JS access for testing
#         secure=False,
#         samesite="lax",
#         max_age=3600,
#         path="/"
#     )
#     return {"message": "Test cookie set"}


    



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
            key="app_jwt_token",
            value=token,
            httponly=True,
            secure=os.getenv("NODE_ENV") == "production",
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/"
        )


        return {"message": F"Authenticated{user}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
    

@router.post("/logout")
async def logout(response: Response):
    """
    Log out by clearing the jwtToken cookie.
    """
    print("logout....")

    response.delete_cookie(
        key="app_jwt_token_auth",    
        # httponly=True,           
        # secure=False,            
        # samesite="lax",             
        path="/",
    )
    return {"message": "Logged out successfully"}





@router.post("/set_cookie")
async def create_cookie(response: Response, request:LoginRequest,  db: AsyncSession = Depends(get_async_db) ):

    user = await AuthenticationService.verify_user(db, request.username, request.password)

    print(f"user data")
    
    print(f"{user}")
                 
    token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )

    print(f"token ... {token}")  
        
    response.set_cookie(
        key="our_cookie",
          value=token,
            httponly=True,
            secure=False,
            samesite="lax"
            )              
    return {"cookie_setted": True}    