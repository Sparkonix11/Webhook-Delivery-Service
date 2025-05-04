from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

from app.api import deps
from app.core.config import settings
from app.redis import redis_client
from app.workers.celery_app import celery_app  # Import the Celery app

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(deps.get_db)):
    """Health check endpoint that verifies all dependencies"""
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        
        # Check Redis connection
        redis_client.ping()
        
        # Check Celery worker using the Celery inspection API
        celery_status = "healthy"
        try:
            # Get stats about registered workers
            inspector = celery_app.control.inspect()
            active_workers = inspector.active()
            
            if not active_workers:
                celery_status = "degraded"
        except Exception as e:
            celery_status = "degraded"
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "celery": celery_status
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }, 503