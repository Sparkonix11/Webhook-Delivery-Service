import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock
import httpx

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.crud import crud_subscription, crud_delivery
from app.api.schemas.subscription import SubscriptionCreate
from app.api.schemas.webhook import WebhookPayload
from app.api.main import app

client = TestClient(app)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    yield Session(engine)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_httpx():
    with patch("httpx.AsyncClient") as mock:
        yield mock


def test_ingest_webhook_success(db: Session):
    # Create a subscription first
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret",
            event_types=["order.created"]
        )
    )
    
    webhook_data = {
        "event_type": "order.created",
        "payload": {"order_id": "123", "status": "created"}
    }
    
    response = client.post("/webhooks/ingest", json=webhook_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["subscription_id"] == str(subscription.id)


def test_ingest_webhook_invalid_event_type(db: Session):
    # Create a subscription first
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret",
            event_types=["order.created"]
        )
    )
    
    webhook_data = {
        "event_type": "order.updated",  # Not in allowed event types
        "payload": {"order_id": "123", "status": "updated"}
    }
    
    response = client.post("/webhooks/ingest", json=webhook_data)
    assert response.status_code == 400
    assert "Event type not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_process_webhook_delivery_success(db: Session, mock_httpx):
    # Create a subscription
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret"
        )
    )
    
    # Create a delivery task
    task = crud_delivery.create(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "data"},
            "attempt_count": 0
        }
    )
    
    # Mock successful HTTP response
    mock_client = MagicMock()
    mock_client.post.return_value = httpx.Response(200, json={"status": "ok"})
    mock_httpx.return_value.__aenter__.return_value = mock_client
    
    # Process the delivery
    from app.workers.tasks import process_webhook_delivery
    await process_webhook_delivery(task.id)
    
    # Verify task is completed
    updated_task = crud_delivery.get(db, id=task.id)
    assert updated_task.status == "completed"
    assert updated_task.attempt_count == 1


@pytest.mark.asyncio
async def test_process_webhook_delivery_retry(db: Session, mock_httpx):
    # Create a subscription
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret"
        )
    )
    
    # Create a delivery task
    task = crud_delivery.create(
        db,
        obj_in={
            "subscription_id": subscription.id,
            "payload": {"test": "data"},
            "attempt_count": 0
        }
    )
    
    # Mock failed HTTP response
    mock_client = MagicMock()
    mock_client.post.return_value = httpx.Response(500, json={"error": "server error"})
    mock_httpx.return_value.__aenter__.return_value = mock_client
    
    # Process the delivery
    from app.workers.tasks import process_webhook_delivery
    await process_webhook_delivery(task.id)
    
    # Verify task is retrying
    updated_task = crud_delivery.get(db, id=task.id)
    assert updated_task.status == "retrying"
    assert updated_task.attempt_count == 1
    assert updated_task.next_attempt_at is not None 