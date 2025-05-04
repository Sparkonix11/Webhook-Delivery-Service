import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch
from uuid import uuid4

from app.db.base import Base
from app.db.session import engine
from app.crud import crud_delivery
from app.workers.cleanup import cleanup_old_logs
from app.db.models.delivery_log import DeliveryStatus


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    yield Session(engine)
    Base.metadata.drop_all(bind=engine)


def test_cleanup_old_logs(db: Session):
    # Create some old logs
    old_time = datetime.utcnow() - timedelta(hours=73)  # Older than 72 hours
    recent_time = datetime.utcnow() - timedelta(hours=24)  # Within retention period
    
    # Create old logs
    for i in range(3):
        crud_delivery.create_delivery_log(
            db,
            task_id=uuid4(),
            subscription_id=uuid4(),
            target_url=f"http://example.com/{i}",
            attempt_number=1,
            status=DeliveryStatus.SUCCESS,
            status_code=200
        )
    
    # Create recent logs
    for i in range(2):
        crud_delivery.create_delivery_log(
            db,
            task_id=uuid4(),
            subscription_id=uuid4(),
            target_url=f"http://example.com/recent-{i}",
            attempt_number=1,
            status=DeliveryStatus.SUCCESS,
            status_code=200
        )
    
    # Run cleanup
    with patch("app.core.config.settings.LOG_RETENTION_HOURS", 72):
        deleted_count = cleanup_old_logs(db)
    
    # Verify results
    assert deleted_count == 3  # Only old logs should be deleted
    remaining_logs = db.query(crud_delivery.DeliveryLog).count()
    assert remaining_logs == 2  # Recent logs should remain


def test_cleanup_with_error(db: Session):
    # Create some logs
    for i in range(2):
        crud_delivery.create_delivery_log(
            db,
            task_id=uuid4(),
            subscription_id=uuid4(),
            target_url=f"http://example.com/{i}",
            attempt_number=1,
            status=DeliveryStatus.SUCCESS,
            status_code=200
        )
    
    # Mock the cleanup function to raise an exception
    with patch("app.workers.cleanup.cleanup_old_logs", side_effect=Exception("Cleanup failed")):
        with pytest.raises(Exception):
            cleanup_old_logs(db)
    
    # Verify logs still exist
    remaining_logs = db.query(crud_delivery.DeliveryLog).count()
    assert remaining_logs == 2 