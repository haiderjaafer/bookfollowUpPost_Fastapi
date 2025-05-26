from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.database.config import settings
from sqlalchemy.exc import OperationalError


engine = create_engine(
    settings.sqlalchemy_database_url,
    connect_args={"unicode_results": True},
    fast_executemany=True,
    echo=False,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30
)


#print("Using DB URL:", settings.sqlalchemy_database_url)



SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except OperationalError as e:
        raise ConnectionError("Could not connect to SQL Server") from e    
    finally:
        db.close()
