import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.crud import crud_subscription
from app.api.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.api.main import app

client = TestClient(app)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    yield Session(engine)
    Base.metadata.drop_all(bind=engine)


def test_create_subscription(db: Session):
    subscription_data = {
        "target_url": "https://example.com/webhook",
        "secret": "test_secret",
        "event_types": ["order.created", "user.updated"]
    }
    response = client.post("/subscriptions", json=subscription_data)
    assert response.status_code == 200
    data = response.json()
    assert data["target_url"] == subscription_data["target_url"]
    assert data["event_types"] == subscription_data["event_types"]
    assert "id" in data


def test_get_subscription(db: Session):
    # Create a subscription first
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret",
            event_types=["order.created"]
        )
    )
    
    response = client.get(f"/subscriptions/{subscription.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(subscription.id)
    assert data["target_url"] == subscription.target_url


def test_update_subscription(db: Session):
    # Create a subscription first
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret"
        )
    )
    
    update_data = {
        "target_url": "https://example.com/new-webhook",
        "event_types": ["order.updated"]
    }
    
    response = client.put(f"/subscriptions/{subscription.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["target_url"] == update_data["target_url"]
    assert data["event_types"] == update_data["event_types"]


def test_delete_subscription(db: Session):
    # Create a subscription first
    subscription = crud_subscription.create(
        db,
        obj_in=SubscriptionCreate(
            target_url="https://example.com/webhook",
            secret="test_secret"
        )
    )
    
    response = client.delete(f"/subscriptions/{subscription.id}")
    assert response.status_code == 200
    
    # Verify it's deleted
    response = client.get(f"/subscriptions/{subscription.id}")
    assert response.status_code == 404


def test_list_subscriptions(db: Session):
    # Create multiple subscriptions
    for i in range(3):
        crud_subscription.create(
            db,
            obj_in=SubscriptionCreate(
                target_url=f"https://example.com/webhook-{i}",
                secret="test_secret"
            )
        )
    
    response = client.get("/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3 