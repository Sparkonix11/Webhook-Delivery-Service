import pytest
import uuid
import json
from unittest import mock
import time
from datetime import datetime, timedelta

from app.db.models.delivery_task import DeliveryStatus as TaskStatus
from app.db.models.delivery_log import DeliveryStatus as LogStatus
from app.workers.tasks import process_webhook_delivery, deliver_webhook
from app.services.cache import redis_client
from tests.utils import (
    create_test_subscription,
    create_test_delivery_task,
    MockHTTPClient,
    simulate_failed_dependencies
)


class TestWebhookFlowIntegration:
    """Integration tests for the complete webhook delivery flow"""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, db_session):
        """Setup and teardown for each test - automatically applied to all tests"""
        # Store created objects for clean-up
        self.created_subscriptions = []
        self.created_tasks = []
        
        # Run the test
        yield
        
        # Clean up all created test objects
        try:
            # First clear tasks
            for task_id in self.created_tasks:
                db_session.query(DeliveryLog).filter(
                    DeliveryLog.delivery_task_id == task_id
                ).delete(synchronize_session=False)
            
            # Then delete tasks
            for task_id in self.created_tasks:
                db_session.query(task.__class__).filter(
                    task.__class__.id == task_id
                ).delete(synchronize_session=False)
            
            # Finally delete subscriptions
            for subscription_id in self.created_subscriptions:
                db_session.query(subscription.__class__).filter(
                    subscription.__class__.id == subscription_id
                ).delete(synchronize_session=False)
                
            db_session.commit()
        except Exception as e:
            # Log the error but don't fail the test
            print(f"Error in test cleanup: {str(e)}")
            db_session.rollback()
        
        # Clear any Redis test keys
        try:
            # Clean up Redis keys used in tests
            test_keys = redis_client.keys('*test*')
            if test_keys:
                redis_client.delete(*test_keys)
        except Exception as e:
            print(f"Error cleaning up Redis: {str(e)}")

    def test_full_successful_webhook_flow(self, db_session, mock_http_client):
        """Test a complete successful webhook flow from task creation to delivery"""
        # 1. Create subscription
        subscription = create_test_subscription(
            db_session,
            target_url="http://example.com/success",
            event_types=["order.created"]
        )
        self.created_subscriptions.append(subscription.id)

        # 2. Create delivery task
        payload = {"order_id": "12345", "total": 99.99, "event_type": "order.created"}
        task = create_test_delivery_task(
            db_session,
            subscription_id=subscription.id,
            payload=payload,
            event_type="order.created"
        )
        self.created_tasks.append(task.id)

        # 3. Process the webhook delivery
        assert process_webhook_delivery(str(task.id)) is True

        # 4. Verify task was completed - using the same db_session
        # Refresh the session to see changes made by the worker
        db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED
        assert task.attempt_count == 1

        # 5. Verify log was created with success status
        logs = db_session.query(DeliveryLog).filter(
            DeliveryLog.delivery_task_id == task.id
        ).all()
        
        assert len(logs) >= 1, "Expected at least one log entry but found none"
        log = logs[0]
        assert log.status == LogStatus.SUCCESS
        assert log.attempt_number == 1
        assert log.status_code == 200

    def test_retry_flow_with_eventual_success(self, db_session):
        """Test that the webhook delivery is retried on failure and eventually succeeds"""
        # 1. Create subscription
        subscription = create_test_subscription(
            db_session, 
            target_url="http://example.com/retry-test"
        )
        self.created_subscriptions.append(subscription.id)
        
        # 2. Create delivery task
        task = create_test_delivery_task(
            db_session,
            subscription_id=subscription.id
        )
        self.created_tasks.append(task.id)
        
        # Setup mock HTTP client to fail first, then succeed
        with mock.patch('app.workers.tasks.httpx.Client') as mock_client:
            # First attempt - simulate server error
            first_client = MockHTTPClient({
                "default": MockHTTPClient.MockHTTPResponse(500, "Server Error")
            })
            mock_client.return_value = first_client
            
            # Process first attempt - should fail but schedule retry
            process_webhook_delivery(str(task.id))
            
            # Check task status after first attempt - using db_session
            db_session.refresh(task)
            assert task.status == TaskStatus.PENDING
            assert task.attempt_count == 1
            assert task.next_attempt_at is not None
            
            # Second attempt - simulate success
            second_client = MockHTTPClient({
                "default": MockHTTPClient.MockHTTPResponse(200, "Success")
            })
            mock_client.return_value = second_client
            
            # Process second attempt - should succeed
            process_webhook_delivery(str(task.id))
            
            # Verify final task state - using db_session
            db_session.refresh(task)
            assert task.status == TaskStatus.COMPLETED
            assert task.attempt_count == 2
            
            # Verify we have two logs - one failure and one success
            logs = db_session.query(DeliveryLog).filter(
                DeliveryLog.delivery_task_id == task.id
            ).order_by(DeliveryLog.created_at).all()
            
            assert len(logs) == 2, "Expected exactly two log entries"
            assert logs[0].status == LogStatus.FAILED_ATTEMPT
            assert logs[0].attempt_number == 1
            assert logs[0].status_code == 500
            
            assert logs[1].status == LogStatus.SUCCESS
            assert logs[1].attempt_number == 2
            assert logs[1].status_code == 200

    def test_max_retries_exceeded(self, db_session):
        """Test that a task is marked as permanently failed after max retries"""
        # 1. Create subscription
        subscription = create_test_subscription(
            db_session, 
            target_url="http://example.com/always-fails"
        )
        self.created_subscriptions.append(subscription.id)
        
        # 2. Create delivery task with attempt_count already at max retries - 1
        from app.core.config import settings
        task = create_test_delivery_task(
            db_session,
            subscription_id=subscription.id,
            attempt_count=settings.WEBHOOK_MAX_RETRIES - 1
        )
        self.created_tasks.append(task.id)
        
        # Setup mock HTTP client to always fail
        with mock.patch('app.workers.tasks.httpx.Client') as mock_client:
            client = MockHTTPClient({
                "default": MockHTTPClient.MockHTTPResponse(500, "Server Error")
            })
            mock_client.return_value = client
            
            # Process the webhook - should fail permanently
            process_webhook_delivery(str(task.id))
            
            # Verify task is marked as failed - using db_session
            db_session.refresh(task)
            assert task.status == TaskStatus.FAILED
            assert task.attempt_count == settings.WEBHOOK_MAX_RETRIES
            
            # Verify failure log
            logs = db_session.query(DeliveryLog).filter(
                DeliveryLog.delivery_task_id == task.id
            ).order_by(DeliveryLog.created_at.desc()).all()
            
            assert len(logs) >= 1, "Expected at least one log entry after maximum retries"
            latest_log = logs[0]
            assert latest_log.status == LogStatus.FAILURE
            assert "Max retries" in latest_log.error_details

    def test_resilience_to_dependency_failures(self, db_session):
        """Test system resilience when dependencies like Redis fail"""
        # 1. Create subscription
        subscription = create_test_subscription(
            db_session, 
            target_url="http://example.com/webhook"
        )
        self.created_subscriptions.append(subscription.id)
        
        # 2. Create delivery task
        task = create_test_delivery_task(
            db_session,
            subscription_id=subscription.id
        )
        self.created_tasks.append(task.id)
        
        # Get our failure simulator
        failures = simulate_failed_dependencies()
        
        # Test Redis failure doesn't prevent delivery (should fall back to DB)
        with failures.redis_down():
            with mock.patch('app.workers.tasks.httpx.Client') as mock_client:
                client = MockHTTPClient({
                    "default": MockHTTPClient.MockHTTPResponse(200, "Success")
                })
                mock_client.return_value = client
                
                # Should succeed despite Redis being down
                result = process_webhook_delivery(str(task.id))
                assert result is True
        
        # Verify task completed - using db_session
        db_session.refresh(task)
        assert task.status == TaskStatus.COMPLETED