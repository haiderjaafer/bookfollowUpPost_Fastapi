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
        # response.set_cookie(
        #     key="jwt_token",
        #     value=token,
        #     httponly=True,
        #     secure=True,        # 🔥 Change this to False for HTTP (local/LAN)
        #     samesite="lax",
        #     max_age=60 * 60 * 24 * 30,
        #     path="/",
        #     # domain="10.20.11.100"  # 🔥 REMOVE — not needed unless using subdomains
        # )

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



        # response.set_cookie(
        #     key="jwt_cookies_auth_token",
        #     value=token,
        #     # httponly=False,           # Prevent JS access
        #     # # secure=os.getenv("NODE_ENV") == "production",            # False for localhost HTTP
        #     secure=False,
        #     # samesite="none",          # Lax for cross-origin in development
        #     max_age=60 * 60 * 24 * 30 ,    # 30 days
        #     # # path="10.20.11.33",                # Available site-wide
        #     # path="localhost"
        #     # # 🔥 DO NOT set domain for localhost
        #     # # domain="127.0.0.1"

        #     domain="10.20.11.33" , # Add this!
        #     httponly=True,
        #     samesite="lax",      # IMPORTANT
        #     # secure=True           # REQUIRED for cross-origin + samesite=none
        # )
        
        # Add explicit headers for debugging
        # response.headers["Access-Control-Allow-Credentials"] = "true"
        
        # logger.info(f"Login successful for user: {user.username}")
        # logger.debug(f"Cookie set: jwtToken (length: {len(token)})")
        
        return {"message": "Login successful", "user": {"id": user.id, "username": user.username}}
        # return {"token":token}
        
             
    except HTTPException as e:
        logger.warning(f"Authentication failed for user {request.username}: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



from fastapi import HTTPException

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
        # print(f"{user_create}")
        user = await AuthenticationService.create_user(db, user_create)

        print(user)

        token = AuthenticationService.generate_jwt(
            user_id=user.id,
            username=user.username,
            permission=user.permission
        )

        # Set HTTP-only cookie
        response.set_cookie(
            key="jwt_cookies_auth_token",
            value=token,
            httponly=True,
            secure=os.getenv("NODE_ENV") == "production",
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
            path="/"
        )

        return {"message": f"Authenticated {user.username}"}

    except HTTPException:
        # Re-raise HTTPExceptions from create_user without changing them -- this will getback detail if error occured
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")
    

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





    