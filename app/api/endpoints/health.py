from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import redis
import httpx

from app.api import deps
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(deps.get_db)):
    """Health check endpoint that verifies all dependencies"""
    try:
        # Check database connection
        db.execute("SELECT 1")
        
        # Check Redis connection
        redis_client = redis.Redis.from_url(settings.REDIS_URL)
        redis_client.ping()
        
        # Check Celery worker
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.CELERY_BROKER_URL}/api/workers")
            response.raise_for_status()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "celery": "connected"
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503 