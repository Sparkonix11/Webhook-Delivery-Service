from celery import Celery
import logging
import os

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Create Celery app
celery_app = Celery(
    "webhook_delivery_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.task_routes = {
    "app.workers.tasks.*": {"queue": "webhooks"},
    "app.workers.cleanup.*": {"queue": "maintenance"},
}

celery_app.conf.beat_schedule = {
    "cleanup-delivery-logs": {
        "task": "app.workers.cleanup.cleanup_old_logs",
        "schedule": 3600.0,  # Run every hour (3600 seconds)
    },
    "cleanup-failed-tasks": {
        "task": "app.workers.cleanup.cleanup_failed_tasks",
        "schedule": 86400.0,  # Run once a day (86400 seconds)
    },
}

# Optional settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,  # Tasks are acknowledged after execution, not when received
    task_reject_on_worker_lost=True,  # Ensure tasks aren't lost when worker is terminated
)