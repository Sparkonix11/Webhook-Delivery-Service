import pytest
from datetime import datetime, timedelta
import uuid

from app.db.models.delivery_log import DeliveryLog, DeliveryStatus as LogStatus
from app.crud.crud_delivery import cleanup_old_logs
from app.core.config import settings


def test_cleanup_old_logs(db):
    """Test that old delivery logs are properly cleaned up."""
    from app.crud import crud_subscription, crud_delivery
    
    # Create a test subscription
    subscription = crud_subscription.create(
        db,
        obj_in={"target_url": "https://webhook.site/cleanup-test", "secret": None}
    )
    
    # Create a test delivery task
    task = crud_delivery.create_delivery_task(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "cleanup"},
            "event_type": None
        }
    )
    
    # Create old logs (older than retention period)
    old_date = datetime.utcnow() - timedelta(hours=settings.LOG_RETENTION_HOURS + 1)
    for i in range(5):
        # Need to create logs directly to set created_at in the past
        log = DeliveryLog(
            id=uuid.uuid4(),
            delivery_task_id=task.id,
            subscription_id=subscription.id,
            target_url=str(subscription.target_url),
            attempt_number=i+1,
            status=LogStatus.SUCCESS,
            status_code=200,
            created_at=old_date
        )
        db.add(log)
    
    # Create recent logs
    for i in range(3):
        crud_delivery.create_delivery_log(
            db,
            task_id=task.id,
            subscription_id=subscription.id,
            target_url=str(subscription.target_url),
            attempt_number=i+1,
            status=LogStatus.SUCCESS,
            status_code=200
        )
    
    db.commit()
    
    # Verify we have 8 logs total
    logs = db.query(DeliveryLog).all()
    assert len(logs) == 8
    
    # Run the cleanup function
    deleted_count = cleanup_old_logs(db)
    
    # Verify that 5 logs were deleted (the old ones)
    assert deleted_count == 5
    
    # Verify only 3 logs remain in the database
    remaining_logs = db.query(DeliveryLog).all()
    assert len(remaining_logs) == 3
    
    # Verify all remaining logs are recent
    retention_cutoff = datetime.utcnow() - timedelta(hours=settings.LOG_RETENTION_HOURS)
    for log in remaining_logs:
        assert log.created_at > retention_cutoff