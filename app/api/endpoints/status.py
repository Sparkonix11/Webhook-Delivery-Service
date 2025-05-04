from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from typing import Dict, Any
import uuid
import time

from app.db.base import get_db
from app.api.schemas import HealthResponse
from app.services.cache import redis_client
from app.workers.celery_app import celery_app

router = APIRouter()


@router.get("/", response_model=HealthResponse)
def get_status(db: Session = Depends(get_db)):
    """
    Check if the service and its dependencies are healthy.
    """
    # Check database connection
    db_status = "healthy"
    db_error = None
    try:
        # Simple query to check database connectivity
        db.execute("SELECT 1").fetchall()
    except Exception as e:
        db_status = "unhealthy"
        db_error = str(e)
    
    # Check Redis connection
    redis_status = "healthy"
    redis_error = None
    try:
        redis_client.ping()
    except Exception as e:
        redis_status = "unhealthy"
        redis_error = str(e)
    
    # Check Celery worker health by sending a ping task
    celery_status = "unknown"
    celery_error = None
    celery_workers = []
    
    try:
        # Get stats about registered workers
        inspector = celery_app.control.inspect()
        active_workers = inspector.active()
        
        if not active_workers:
            celery_status = "unhealthy"
            celery_error = "No active Celery workers found"
        else:
            # Send a ping task to verify task processing
            ping_id = str(uuid.uuid4())
            task_key = f"worker_health_ping:{ping_id}"
            
            # Try to execute a simple task through celery
            result = celery_app.send_task(
                "app.workers.status.ping_worker",
                args=[ping_id],
                kwargs={},
                queue="default",
                expires=10  # Expire task after 10 seconds
            )
            
            # Wait for task result (with timeout)
            start_time = time.time()
            ping_successful = False
            timeout = 5  # 5 second timeout
            
            while time.time() - start_time < timeout:
                # Check if task completed
                if redis_client.exists(task_key):
                    ping_successful = True
                    redis_client.delete(task_key)  # Clean up
                    break
                time.sleep(0.1)
            
            if ping_successful:
                celery_status = "healthy"
                celery_workers = list(active_workers.keys())
            else:
                celery_status = "unhealthy"
                celery_error = f"Worker ping timed out after {timeout} seconds"
                # Revoke the task since it didn't complete in time
                result.revoke(terminate=True)
    except Exception as e:
        celery_status = "unhealthy"
        celery_error = str(e)
    
    # Determine overall health status
    is_healthy = db_status == "healthy" and redis_status == "healthy" and celery_status == "healthy"
    
    # Return appropriate status code
    if not is_healthy:
        raise HTTPException(
            status_code=503,
            detail="Service dependencies are unhealthy"
        )
    
    return {
        "service": "webhook_delivery_service",
        "status": "healthy" if is_healthy else "degraded",
        "dependencies": {
            "database": {"status": db_status, "error": db_error},
            "redis": {"status": redis_status, "error": redis_error},
            "celery": {"status": celery_status, "error": celery_error, "workers": celery_workers}
        }
    }


@router.get("/ready", response_model=Dict[str, Any])
def readiness_probe():
    """
    Kubernetes readiness probe endpoint
    """
    return {"status": "ready"}