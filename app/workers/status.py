import logging
from celery import Task
from app.workers.celery_app import celery_app
from app.services.cache import redis_client

logger = logging.getLogger(__name__)


class StatusTask(Task):
    """Base class for status check tasks"""
    _db = None
    
    def after_return(self, *args, **kwargs):
        """Clean up after task execution"""
        pass


@celery_app.task(base=StatusTask, bind=True)
def ping_worker(self, ping_id: str):
    """
    Simple task to verify worker is processing tasks.
    Sets a Redis key that the status API can check for.
    
    Args:
        ping_id: Unique identifier for this ping request
    """
    logger.debug(f"Worker ping received with id: {ping_id}")
    
    # Set a key in Redis that the status API can check
    task_key = f"worker_health_ping:{ping_id}"
    redis_client.set(task_key, "1", ex=10)  # Expire after 10 seconds
    
    return {"status": "ok", "worker": self.request.hostname}