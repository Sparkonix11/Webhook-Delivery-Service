import pytest
from fastapi.testclient import TestClient
import uuid

from app.api.main import app
from app.db.models import Subscription
from app.core.config import settings


client = TestClient(app)


def test_create_subscription():
    """Test creating a subscription"""
    response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/test-webhook",
            "secret": "test-secret",
            "event_types": ["order.created", "user.updated"]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_url"] == "https://webhook.site/test-webhook"
    assert data["secret"] == "test-secret"
    assert "order.created" in data["event_types"]
    assert "user.updated" in data["event_types"]
    assert "id" in data


def test_get_subscription():
    """Test getting a subscription"""
    # First create a subscription
    response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/get-test",
            "secret": "test-secret-get",
            "event_types": ["order.shipped"]
        },
    )
    assert response.status_code == 200
    subscription_id = response.json()["id"]
    
    # Then get it
    response = client.get(
        f"{settings.API_V1_STR}/subscriptions/{subscription_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_url"] == "https://webhook.site/get-test"
    assert data["secret"] == "test-secret-get"
    assert "order.shipped" in data["event_types"]


def test_update_subscription():
    """Test updating a subscription"""
    # First create a subscription
    response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/update-test",
            "secret": "original-secret",
            "event_types": ["order.created"]
        },
    )
    assert response.status_code == 200
    subscription_id = response.json()["id"]
    
    # Then update it
    response = client.put(
        f"{settings.API_V1_STR}/subscriptions/{subscription_id}",
        json={
            "target_url": "https://webhook.site/updated",
            "event_types": ["order.created", "order.updated"]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_url"] == "https://webhook.site/updated"
    assert data["secret"] == "original-secret"  # Unchanged
    assert "order.created" in data["event_types"]
    assert "order.updated" in data["event_types"]


def test_delete_subscription():
    """Test deleting a subscription"""
    # First create a subscription
    response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/delete-test",
            "secret": "delete-secret",
        },
    )
    assert response.status_code == 200
    subscription_id = response.json()["id"]
    
    # Then delete it
    response = client.delete(
        f"{settings.API_V1_STR}/subscriptions/{subscription_id}"
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Subscription deleted successfully"
    
    # Verify it's gone
    response = client.get(
        f"{settings.API_V1_STR}/subscriptions/{subscription_id}"
    )
    assert response.status_code == 404