from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.users import UserCreate, Users, UserResponse
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

class AuthenticationService:
    @staticmethod
    async def verify_user(db: AsyncSession, username: str, password: str) -> Optional[UserResponse]:
        """
        Verify user credentials and return UserResponse if authenticated.
        
        Args:
            db: AsyncSession for database access
            username: User's username
            password: Plaintext password to verify
            
        Returns:
            UserResponse if authenticated, else raises HTTPException
        """
        try:
            # Query user by username
            result = await db.execute(select(Users).where(Users.username == username))
            user = result.scalars().first()
            
            if not user:
                raise HTTPException(status_code=400, detail="Invalid username or password")
            
            # Verify password
            if not pwd_context.verify(password, user.password):
                raise HTTPException(status_code=400, detail="Invalid username or password")
            
            # Return user data (excluding password)
            return UserResponse(
                id=user.id,
                username=user.username,
                permission=user.permission
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

    @staticmethod
    def generate_jwt(user_id: int, username: str, permission: Optional[str]) -> str:
        """
        Generate a JWT token for the user.
        
        Args:
            user_id: User's ID
            username: User's username
            permission: User's permission level
            
        Returns:
            JWT token as string
        """
        payload = {
            "id": user_id,
            "username": username,
            "isAdmin": permission == "admin" if permission else False,
            "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    



        # app/services/auth.py (add to AuthenticationService)
    @staticmethod
    async def create_user(db: AsyncSession, user_create: UserCreate) -> UserResponse:
        """
        Create a new user with hashed password.
        
        Args:
            db: AsyncSession
            user_create: UserCreate Pydantic model
            
        Returns:
            UserResponse
        """
        hashed_password = pwd_context.hash(user_create.password) if user_create.password else None
        db_user = Users(
            username=user_create.username,
            password=hashed_password,
            permission=user_create.permission
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return UserResponse(
            id=db_user.id,
            username=db_user.username,
            permission=db_user.permission
        )