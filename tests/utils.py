import os
import uuid
import json
import time
import httpx
import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import fakeredis
from unittest import mock

from app.core.config import settings
from app.services.cache import redis_client
from app.db.base import Base, engine
from app.db.models.delivery_task import DeliveryStatus as TaskStatus
from app.db.models.delivery_log import DeliveryStatus as LogStatus
from app.db.models.subscription import Subscription
from app.db.models.delivery_task import DeliveryTask
from app.db.models.delivery_log import DeliveryLog


class MockRedis:
    """Class to mock Redis for testing"""
    def __init__(self):
        self.server = fakeredis.FakeServer()
        self.redis = fakeredis.FakeRedis(server=self.server)
        
    def patch_redis(self):
        """Patch the redis client with a fake redis"""
        return mock.patch('app.services.cache.redis_client', self.redis)


class MockHTTPResponse:
    """Class to mock HTTP responses"""
    def __init__(self, status_code: int = 200, text: str = "", json_data: Dict = None):
        self.status_code = status_code
        self._text = text
        self._json = json_data or {}
    
    @property
    def text(self) -> str:
        return self._text
        
    def json(self) -> Dict:
        return self._json
        
    def raise_for_status(self):
        """Simulate raise_for_status"""
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP Error {self.status_code}", 
                request=httpx.Request('POST', 'http://example.com'), 
                response=self
            )


class MockHTTPClient:
    """Class to mock the HTTP client for testing webhook deliveries"""
    def __init__(self, response_map=None):
        # Default responses for different URLs
        self.response_map = response_map or {
            "default": MockHTTPResponse(200, "OK", {"status": "success"}),
            "error": MockHTTPResponse(500, "Server Error", {"status": "error"}),
            "timeout": None  # None will trigger a timeout exception
        }
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
        
    def post(self, url: str, **kwargs):
        """Mock post method to simulate different responses"""
        # Check if URL contains any of our special response keys
        for key, response in self.response_map.items():
            if key in url:
                if response is None:
                    raise httpx.TimeoutException("Connection timeout")
                return response
        
        # Return default response
        return self.response_map.get("default")


def create_test_subscription(
    db, 
    target_url: str = "http://example.com/webhook", 
    secret: str = "test-secret",
    event_types: List[str] = None
) -> Subscription:
    """Create a test subscription in the database"""
    subscription = Subscription(
        id=uuid.uuid4(),
        target_url=target_url,
        secret=secret,
        event_types=event_types or ["test.event", "user.created"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def create_test_delivery_task(
    db,
    subscription_id: uuid.UUID,
    status: TaskStatus = TaskStatus.PENDING,
    payload: Dict[str, Any] = None,
    event_type: str = "test.event",
    attempt_count: int = 0
) -> DeliveryTask:
    """Create a test delivery task in the database"""
    task = DeliveryTask(
        id=uuid.uuid4(),
        subscription_id=subscription_id,
        status=status,
        payload=payload or {"test": "data"},
        event_type=event_type,
        attempt_count=attempt_count,
        next_attempt_at=datetime.utcnow() if status == TaskStatus.PENDING else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_test_delivery_log(
    db,
    task_id: uuid.UUID,
    subscription_id: uuid.UUID,
    status: LogStatus = LogStatus.SUCCESS,
    attempt_number: int = 1,
    target_url: str = "http://example.com/webhook",
    status_code: Optional[int] = 200,
    error_details: Optional[str] = None
) -> DeliveryLog:
    """Create a test delivery log in the database"""
    log = DeliveryLog(
        id=uuid.uuid4(),
        task_id=task_id,
        subscription_id=subscription_id,
        status=status,
        attempt_number=attempt_number,
        target_url=target_url,
        status_code=status_code,
        error_details=error_details,
        created_at=datetime.utcnow()
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@pytest.fixture(scope="function")
def mock_redis():
    """Fixture to mock Redis for testing"""
    mock_redis = MockRedis()
    with mock_redis.patch_redis():
        yield mock_redis.redis


@pytest.fixture(scope="function")
def mock_http_client():
    """Fixture to mock HTTP client for testing webhook deliveries"""
    with mock.patch('app.workers.tasks.httpx.Client') as mock_client:
        client_instance = MockHTTPClient()
        mock_client.return_value = client_instance
        yield client_instance


def simulate_failed_dependencies():
    """Helper function to simulate failures in dependencies"""
    
    # Interface for simulating infrastructure failures
    class FailureSimulator:
        @staticmethod
        def redis_down():
            """Simulate Redis being down"""
            with mock.patch('app.services.cache.redis_client.get', side_effect=Exception("Redis connection error")):
                yield
        
        @staticmethod
        def db_down():
            """Simulate database being down"""
            with mock.patch('sqlalchemy.orm.Session.query', side_effect=Exception("Database connection error")):
                yield
        
        @staticmethod
        def http_timeout():
            """Simulate HTTP timeouts"""
            with mock.patch('app.workers.tasks.httpx.Client') as mock_client:
                client = MockHTTPClient({"default": None})  # All requests timeout
                mock_client.return_value = client
                yield
        
        @staticmethod
        def slow_db():
            """Simulate slow database queries"""
            def slow_execute(original_execute, *args, **kwargs):
                time.sleep(0.5)  # Add 500ms delay
                return original_execute(*args, **kwargs)
            
            original = engine.execute
            try:
                engine.execute = lambda *args, **kwargs: slow_execute(original, *args, **kwargs)
                yield
            finally:
                engine.execute = original
    
    return FailureSimulator