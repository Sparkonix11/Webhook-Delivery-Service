from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc
from uuid import UUID
from datetime import datetime, timedelta

from app.db.models.delivery_task import DeliveryTask, DeliveryStatus as TaskStatus
from app.db.models.delivery_log import DeliveryLog, DeliveryStatus as LogStatus
from app.api.schemas.delivery import DeliveryTaskCreate
from app.core.config import settings


def create_delivery_task(db: Session, *, obj_in: DeliveryTaskCreate) -> DeliveryTask:
    """Create a new delivery task."""
    db_obj = DeliveryTask(
        subscription_id=obj_in.subscription_id,
        payload=obj_in.payload,
        event_type=obj_in.event_type,
        status=TaskStatus.PENDING,
        attempt_count=0,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_task(db: Session, id: UUID) -> Optional[DeliveryTask]:
    """Get a delivery task by ID."""
    return db.query(DeliveryTask).filter(DeliveryTask.id == id).first()


def get_pending_tasks(db: Session, limit: int = 10) -> List[DeliveryTask]:
    """Get pending delivery tasks."""
    now = datetime.utcnow()
    return db.query(DeliveryTask).filter(
        (DeliveryTask.status == TaskStatus.PENDING) &
        ((DeliveryTask.next_attempt_at.is_(None)) | (DeliveryTask.next_attempt_at <= now))
    ).limit(limit).all()


def update_task_status(
    db: Session, *, task_id: UUID, status: TaskStatus, 
    next_attempt_at: Optional[datetime] = None,
    increment_attempt: bool = False  # Add flag to control increment
) -> DeliveryTask:
    """Update a delivery task status."""
    task = db.query(DeliveryTask).filter(DeliveryTask.id == task_id).first()
    
    if task:
        task.status = status
        if increment_attempt:  # Only increment if flag is True
            task.attempt_count += 1
        task.next_attempt_at = next_attempt_at
        
        db.add(task)
        db.commit()
        db.refresh(task)
    
    return task


def create_delivery_log(
    db: Session, *, 
    task_id: UUID, 
    subscription_id: UUID,
    target_url: str,
    attempt_number: int, 
    status: LogStatus,
    status_code: Optional[int] = None,
    error_details: Optional[str] = None
) -> DeliveryLog:
    """Create a delivery log entry."""
    log = DeliveryLog(
        delivery_task_id=task_id,
        subscription_id=subscription_id,
        target_url=target_url,
        attempt_number=attempt_number,
        status=status,
        status_code=status_code,
        error_details=error_details
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_task_logs(db: Session, task_id: UUID) -> List[DeliveryLog]:
    """Get all logs for a specific delivery task."""
    return db.query(DeliveryLog).filter(
        DeliveryLog.delivery_task_id == task_id
    ).order_by(DeliveryLog.attempt_number).all()


def get_subscription_logs(
    db: Session, subscription_id: UUID, limit: int = 20
) -> List[DeliveryLog]:
    """Get recent logs for a specific subscription."""
    return db.query(DeliveryLog).filter(
        DeliveryLog.subscription_id == subscription_id
    ).order_by(desc(DeliveryLog.created_at)).limit(limit).all()


def cleanup_old_logs(db: Session) -> int:
    """Delete logs older than the retention period."""
    retention_hours = settings.LOG_RETENTION_HOURS
    cutoff_date = datetime.utcnow() - timedelta(hours=retention_hours)
    
    deleted_count = db.query(DeliveryLog).filter(
        DeliveryLog.created_at < cutoff_date
    ).delete(synchronize_session=False)
    
    db.commit()
    return deleted_count