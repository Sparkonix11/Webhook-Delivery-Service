from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.core.config import settings
from app.services.cache import redis_client

def get_db_session() -> Generator[Session, None, None]:
    """Get database session dependency"""
    db = get_db()
    try:
        yield db
    finally:
        db.close()

def get_redis_client():
    """Get Redis client dependency"""
    return redis_client 