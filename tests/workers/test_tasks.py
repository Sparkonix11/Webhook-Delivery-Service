import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app.workers.tasks import deliver_webhook, process_webhook_delivery
from app.db.models.delivery_task import DeliveryStatus as TaskStatus
from app.db.models.delivery_log import DeliveryStatus as LogStatus
from app.services.cache import cache_subscription, get_cached_subscription


def test_deliver_webhook_success():
    """Test successful webhook delivery."""
    target_url = "https://webhook.site/test"
    payload = {"test": "data"}
    
    # Mock successful HTTP response
    with patch('httpx.Client') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = deliver_webhook(target_url, payload)
        
        assert result["success"] is True
        assert result["status_code"] == 200


def test_deliver_webhook_failure():
    """Test failed webhook delivery."""
    target_url = "https://webhook.site/test"
    payload = {"test": "data"}
    
    # Mock failed HTTP response
    with patch('httpx.Client') as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        result = deliver_webhook(target_url, payload)
        
        assert result["success"] is False
        assert result["status_code"] == 500
        assert "error" in result


def test_deliver_webhook_network_error():
    """Test webhook delivery with network error."""
    target_url = "https://webhook.site/test"
    payload = {"test": "data"}
    
    # Mock network error
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.post.side_effect = Exception("Network error")
        
        result = deliver_webhook(target_url, payload)
        
        assert result["success"] is False
        assert "error" in result
        assert "Unexpected error" in result["error"]


@pytest.mark.parametrize("use_cache", [True, False])
def test_process_webhook_delivery(db, use_cache):
    """Test processing a webhook delivery task, with and without cache."""
    from app.crud import crud_subscription, crud_delivery
    
    # Create a test subscription
    subscription = crud_subscription.create(
        db,
        obj_in={"target_url": "https://webhook.site/test-process", "secret": None}
    )
    
    # Create a test delivery task
    task = crud_delivery.create_delivery_task(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "process_task"},
            "event_type": None
        }
    )
    
    # If testing with cache, add the subscription to cache
    if use_cache:
        cache_subscription(
            subscription.id,
            {
                "id": str(subscription.id),
                "target_url": str(subscription.target_url),
                "secret": subscription.secret,
                "event_types": subscription.event_types
            }
        )
        # Verify it's in cache
        cached = get_cached_subscription(subscription.id)
        assert cached is not None
        assert cached["target_url"] == str(subscription.target_url)
    
    # Mock the deliver_webhook function for a successful delivery
    with patch('app.workers.tasks.deliver_webhook') as mock_deliver:
        mock_deliver.return_value = {"success": True, "status_code": 200}
        
        # Process the task
        result = process_webhook_delivery(str(task.id))
        
        # Verify the task was processed successfully
        assert result is True
        
        # Refresh the task from DB
        db.refresh(task)
        assert task.status == TaskStatus.COMPLETED
        
        # Verify a log entry was created
        logs = crud_delivery.get_task_logs(db, task.id)
        assert len(logs) == 1
        assert logs[0].status == LogStatus.SUCCESS
        assert logs[0].status_code == 200


def test_process_webhook_delivery_with_retry(db):
    """Test webhook delivery with retry after failure."""
    from app.crud import crud_subscription, crud_delivery
    from app.core.config import settings
    
    # Create a test subscription
    subscription = crud_subscription.create(
        db,
        obj_in={"target_url": "https://webhook.site/test-retry", "secret": None}
    )
    
    # Create a test delivery task
    task = crud_delivery.create_delivery_task(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "retry"},
            "event_type": None
        }
    )
    
    # Mock the deliver_webhook function for a failed delivery
    with patch('app.workers.tasks.deliver_webhook') as mock_deliver:
        mock_deliver.return_value = {
            "success": False, 
            "status_code": 500,
            "error": "Server error"
        }
        
        # Process the task
        result = process_webhook_delivery(str(task.id))
        
        # Verify the task was not processed successfully
        assert result is False
        
        # Refresh the task from DB
        db.refresh(task)
        
        # Verify the task is scheduled for retry
        assert task.status == TaskStatus.PENDING
        assert task.attempt_count == 1
        assert task.next_attempt_at is not None
        
        # Verify proper retry delay was applied (first retry)
        expected_delay = settings.WEBHOOK_RETRY_DELAYS[0]
        expected_time = datetime.utcnow() + timedelta(seconds=expected_delay)
        time_diff = abs((expected_time - task.next_attempt_at).total_seconds())
        assert time_diff < 5  # Allow for small timing differences
        
        # Verify a log entry was created with failed_attempt status
        logs = crud_delivery.get_task_logs(db, task.id)
        assert len(logs) == 1
        assert logs[0].status == LogStatus.FAILED_ATTEMPT
        assert logs[0].error_details == "Server error"


def test_max_retries_exceeded(db):
    """Test that a task is marked as failed after max retries."""
    from app.crud import crud_subscription, crud_delivery
    from app.core.config import settings
    
    # Create a test subscription
    subscription = crud_subscription.create(
        db,
        obj_in={"target_url": "https://webhook.site/test-max-retries", "secret": None}
    )
    
    # Create a test delivery task with attempt_count = max_retries
    task = crud_delivery.create_delivery_task(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "max_retries"},
            "event_type": None
        }
    )
    
    # Set the attempt_count to max_retries
    task.attempt_count = settings.WEBHOOK_MAX_RETRIES
    db.add(task)
    db.commit()
    
    # Mock the deliver_webhook function for a failed delivery
    with patch('app.workers.tasks.deliver_webhook') as mock_deliver:
        mock_deliver.return_value = {
            "success": False, 
            "status_code": 500,
            "error": "Persistent server error"
        }
        
        # Process the task
        result = process_webhook_delivery(str(task.id))
        
        # Verify the task was not processed successfully
        assert result is False
        
        # Refresh the task from DB
        db.refresh(task)
        
        # Verify the task is marked as permanently failed
        assert task.status == TaskStatus.FAILED
        
        # Verify a log entry was created with failure status
        logs = crud_delivery.get_task_logs(db, task.id)
        assert len(logs) == 1
        assert logs[0].status == LogStatus.FAILURE
        assert "Max retries" in logs[0].error_details