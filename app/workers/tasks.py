import logging
from celery import Task
import httpx
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import uuid
from sqlalchemy.exc import SQLAlchemyError

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.db.base import SessionLocal
from app.db.models import Subscription
from app.db.models.delivery_task import DeliveryTask, DeliveryStatus as TaskStatus
from app.db.models.delivery_log import DeliveryLog, DeliveryStatus as LogStatus
from app.crud import crud_subscription, crud_delivery
from app.services import cache

logger = logging.getLogger(__name__)

# Define retry backoff intervals in seconds as per SRS
RETRY_BACKOFF_INTERVALS = [10, 30, 60, 300, 900]  # 10s, 30s, 1m, 5m, 15m
MAX_RETRIES = 5


def calculate_next_attempt_time(attempt_count: int) -> datetime:
    """Calculate the next attempt time based on the attempt count"""
    if attempt_count >= len(RETRY_BACKOFF_INTERVALS):
        return None  # No more retries
    return datetime.utcnow() + timedelta(seconds=RETRY_BACKOFF_INTERVALS[attempt_count])


class WebhookTask(Task):
    """Base class for webhook tasks, providing database session handling"""
    _db = None
    _last_global_version = None
    
    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        """Close the database connection after task execution"""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=WebhookTask, bind=True, max_retries=MAX_RETRIES)
def process_webhook_delivery(self, task_id: str):
    """Process a webhook delivery task"""
    logger.info(f"Processing webhook delivery task: {task_id}")
    
    # Check global cache version to detect subscription changes
    current_global_version = cache.get_cache_version()
    if self.__class__._last_global_version is not None and current_global_version != self.__class__._last_global_version:
        logger.info("Global subscription cache version changed - subscriptions may have been updated")
    # Update the class-level tracker for next run
    self.__class__._last_global_version = current_global_version
    
    try:
        task_uuid = uuid.UUID(task_id)
        db = self.db

        # Get task info and prepare for delivery
        delivery_info = _prepare_webhook_delivery(db, task_uuid)
        if not delivery_info:
            return False
        
        # Deliver the webhook outside any transaction
        delivery_result = deliver_webhook(
            target_url=delivery_info['target_url'],
            payload=delivery_info['payload']
        )
        
        # Handle the result
        return _process_delivery_result(db, task_uuid, delivery_info, delivery_result)
        
    except SQLAlchemyError as e:
        logger.exception(f"Database error while processing webhook task {task_id}")
        if 'db' in locals() and hasattr(db, 'is_active') and db.is_active:
            db.rollback()
            
        # Retry on database errors with exponential backoff
        retry_count = self.request.retries if hasattr(self.request, 'retries') else 0
        if retry_count < MAX_RETRIES:
            retry_delay = RETRY_BACKOFF_INTERVALS[retry_count]
            logger.info(f"Retrying task {task_id} in {retry_delay} seconds (attempt {retry_count + 1}/{MAX_RETRIES})")
            self.retry(countdown=retry_delay, exc=e)
        
        return False
    except Exception as e:
        logger.exception(f"Error processing webhook delivery task: {task_id}")
        if 'db' in locals() and hasattr(db, 'is_active') and db.is_active:
            db.rollback()
        return False


def _prepare_webhook_delivery(db: Session, task_uuid: uuid.UUID) -> dict:
    """Prepare a webhook for delivery - separated for better transaction management"""
    try:
        # Start a transaction
        with db.begin():
            # Get the delivery task with FOR UPDATE lock to prevent race conditions
            task = db.query(DeliveryTask).filter(
                DeliveryTask.id == task_uuid
            ).with_for_update().first()
            
            if not task:
                logger.error(f"Delivery task not found: {task_uuid}")
                return None
                
            if task.status == TaskStatus.COMPLETED:
                logger.info(f"Task already completed: {task_uuid}")
                return None
                
            if task.status == TaskStatus.FAILED:
                logger.info(f"Task already failed: {task_uuid}")
                return None
                
            # Additional check: if task is already in progress, don't process it again
            if task.status == TaskStatus.IN_PROGRESS and task.attempt_count > 0:
                logger.info(f"Task is already being processed: {task_uuid}")
                return None
            
            # Fetch the subscription to get the target URL
            subscription = db.query(Subscription).filter(
                Subscription.id == task.subscription_id
            ).first()
            
            if not subscription:
                logger.error(f"Subscription not found for task: {task_uuid}")
                return None
                
            # Update task status to in_progress
            task.status = TaskStatus.IN_PROGRESS
            task.attempt_count += 1
            db.add(task)
            
            return {
                'target_url': subscription.target_url,
                'payload': task.payload,
                'task': task
            }
            
    except Exception as e:
        logger.exception(f"Error preparing webhook delivery: {task_uuid}")
        raise


def _process_delivery_result(db: Session, task_uuid: uuid.UUID, delivery_info: dict, delivery_result: dict) -> bool:
    """Process the result of a webhook delivery"""
    try:
        # Get a reference to the task (no transaction yet)
        task = delivery_info['task']
        
        # Create delivery log entry - This has its own transaction inside the function
        log = crud_delivery.create_delivery_log(
            db,
            task_id=task_uuid,
            subscription_id=task.subscription_id,
            target_url=delivery_info['target_url'],
            attempt_number=task.attempt_count,
            status=delivery_result['status'],
            status_code=delivery_result.get('status_code'),
            error_details=delivery_result.get('error_details')
        )
        
        # Now use the crud utility to update task status
        if delivery_result['status'] == LogStatus.SUCCESS:
            # Use the dedicated function to update task status
            crud_delivery.update_task_status(
                db, 
                task_id=task_uuid,
                status=TaskStatus.COMPLETED,
                next_attempt_at=None
            )
            logger.info(f"Task {task_uuid} marked as COMPLETED after successful delivery")
            return True
            
        elif delivery_result['status'] == LogStatus.FAILED_ATTEMPT:
            if task.attempt_count < task.max_retries:
                next_attempt = calculate_next_attempt_time(task.attempt_count)
                if next_attempt:
                    # Update to pending with next attempt time
                    crud_delivery.update_task_status(
                        db,
                        task_id=task_uuid,
                        status=TaskStatus.PENDING,
                        next_attempt_at=next_attempt
                    )
                    
                    # Schedule next attempt
                    process_webhook_delivery.apply_async(
                        args=[str(task_uuid)],
                        countdown=(next_attempt - datetime.utcnow()).total_seconds()
                    )
                    return True
            
            # If we get here, we've exceeded max retries
            crud_delivery.update_task_status(
                db,
                task_id=task_uuid,
                status=TaskStatus.FAILED,
                next_attempt_at=None
            )
            logger.info(f"Task {task_uuid} marked as FAILED after maximum retries")
            return False
            
        else:  # LogStatus.FAILURE
            # Mark as permanently failed
            crud_delivery.update_task_status(
                db,
                task_id=task_uuid,
                status=TaskStatus.FAILED,
                next_attempt_at=None
            )
            logger.info(f"Task {task_uuid} marked as FAILED due to permanent failure")
            return False
            
    except Exception as e:
        logger.exception(f"Error processing delivery result: {task_uuid}")
        # No need to rollback as we're using the CRUD utility functions
        # which handle their own transactions
        raise


def deliver_webhook(target_url: str, payload: dict) -> dict:
    """Deliver a webhook payload to the target URL"""
    try:
        # Set timeout as per SRS (5-10 seconds)
        with httpx.Client(timeout=10.0) as client:
            response = client.post(target_url, json=payload)
            
            # Return success response
            return {
                "success": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "status": LogStatus.SUCCESS if 200 <= response.status_code < 300 else LogStatus.FAILED_ATTEMPT,
                "error": f"HTTP {response.status_code}" if response.status_code >= 400 else None,
                "error_details": None if 200 <= response.status_code < 300 else f"HTTP {response.status_code}"
            }
            
    except Exception as e:
        # Return error response
        return {
            "success": False,
            "status_code": None,
            "status": LogStatus.FAILED_ATTEMPT,
            "error": f"Unexpected error: {str(e)}",
            "error_details": str(e)
        }