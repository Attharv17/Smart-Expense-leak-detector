"""
database.py
-----------
Handles the SQLite database connection using SQLAlchemy.
- Creates the engine pointing to a local SQLite file (expenses.db)
- Provides a session factory for dependency injection in routes
- Exposes the declarative Base for model definitions
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database file path (created automatically on first run)
DATABASE_URL = "sqlite:///./expenses.db"

# Create the SQLAlchemy engine
# connect_args is required for SQLite to allow multi-threaded access
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Session factory — each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session per request.
    Ensures the session is always closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
