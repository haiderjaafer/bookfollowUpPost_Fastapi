from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from app.database.config import settings
from contextlib import asynccontextmanager
from typing import AsyncGenerator


# Create async engine for SQL Server using aioodbc
engine = create_async_engine(
    settings.sqlalchemy_database_url,  # must be mssql+aioodbc://
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30
)

# Async sessionmaker
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for ORM models
Base = declarative_base()

# The async with statement automatically closes the session after the response is sent, even if an exception occurs inside the route. 
# FastAPI handles the generator behind the scenes using contextlib.aclosing().
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# And FastAPI will automatically:

# Open the session when the request starts.

# Close it after the request finishes or if an error occurs
