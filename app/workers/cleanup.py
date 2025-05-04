import logging
from celery import Task
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.workers.celery_app import celery_app
from app.db.base import SessionLocal
from app.crud import crud_delivery
from app.core.config import settings
from app.db.models.delivery_task import DeliveryStatus
from app.db.models.delivery_log import DeliveryLog

logger = logging.getLogger(__name__)

# Log retention period in hours as per SRS
LOG_RETENTION_HOURS = 72


class MaintenanceTask(Task):
    """Base class for maintenance tasks with database session handling"""
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        """Close the database connection after task execution"""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=MaintenanceTask, bind=True)
def cleanup_old_logs(self):
    """Clean up delivery logs older than the retention period"""
    logger.info("Starting cleanup of old delivery logs")
    
    try:
        db = self.db
        retention_threshold = datetime.utcnow() - timedelta(hours=LOG_RETENTION_HOURS)
        
        # Delete logs older than retention period
        deleted_count = db.query(DeliveryLog).filter(
            DeliveryLog.created_at < retention_threshold
        ).delete()
        
        db.commit()
        logger.info(f"Deleted {deleted_count} old delivery logs")
        
        return deleted_count
    
    except Exception as e:
        logger.exception("Error during log cleanup")
        if 'db' in locals():
            db.rollback()
        return 0


@celery_app.task(base=MaintenanceTask, bind=True)
def cleanup_failed_tasks(self):
    """Clean up failed delivery tasks older than the retention period."""
    logger.info("Starting failed tasks cleanup")
    
    try:
        db = self.db
        retention_days = settings.FAILED_TASK_RETENTION_DAYS
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Begin transaction
        with db.begin():
            # Find failed tasks older than retention period
            query = db.query(crud_delivery.model).filter(
                crud_delivery.model.status == DeliveryStatus.FAILED,
                crud_delivery.model.updated_at < cutoff_date
            )
            
            # Count for logging
            count = query.count()
            
            if count > 0:
                # Delete the tasks
                query.delete(synchronize_session=False)
                logger.info(f"Failed task cleanup completed: {count} tasks removed")
            else:
                logger.info("No failed tasks to clean up")
        
        return count
    
    except Exception as e:
        logger.exception("Error performing failed tasks cleanup")
        return 0


# Schedule the cleanup task to run every hour
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(hours=1).total_seconds(),
        cleanup_old_logs.s(),
        name='cleanup-old-logs'
    )