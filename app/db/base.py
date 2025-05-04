from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.core.config import settings

# Configure engine with proper connection pooling settings
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    pool_pre_ping=True,
    pool_size=settings.DB_CONNECTION_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=30,  # Wait up to 30 seconds for a connection
    pool_recycle=1800  # Recycle connections after 30 minutes
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Optional context manager for non-FastAPI usage
@contextmanager
def get_db_context():
    """Context manager for getting a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()