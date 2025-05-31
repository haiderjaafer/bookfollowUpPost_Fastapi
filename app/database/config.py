from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
import urllib.parse
from fastapi import APIRouter

# Initialize the router
bookFollowUpRouter = APIRouter()

# ================= Configuration =================
class Settings(BaseSettings):
    DATABASE_SERVER: str
    DATABASE_NAME: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_DRIVER: str = "ODBC Driver 17 for SQL Server"
    PDF_UPLOAD_PATH: Path  # Use Path type instead of str
    PDF_SOURCE_PATH: Path  # Use Path type instead of str
    MODE: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"  # Ensure proper encoding

    # Validator to ensure paths exist and are directories
    @field_validator("PDF_UPLOAD_PATH", "PDF_SOURCE_PATH")
    def validate_paths(cls, value: Path) -> Path:
        value = Path(value)  # Convert to Path object if not already
        if not value.exists():
            raise ValueError(f"Path {value} does not exist")
        if not value.is_dir():
            raise ValueError(f"Path {value} is not a directory")
        return value.resolve()  # Resolve to absolute path

    @property
    def sqlalchemy_database_url(self) -> str:
        params = urllib.parse.quote_plus(
            f"DRIVER={self.DATABASE_DRIVER};"
            f"SERVER={self.DATABASE_SERVER};"
            f"DATABASE={self.DATABASE_NAME};"
            f"UID={self.DATABASE_USER};"
            f"PWD={self.DATABASE_PASSWORD};"
            f"TrustServerCertificate=yes;"
            f"MARS_Connection=Yes;"
            f"CHARSET=UTF8;"
        )
        return f"mssql+aioodbc:///?odbc_connect={params}"


# Instantiate settings
settings = Settings()

# Route to test paths
