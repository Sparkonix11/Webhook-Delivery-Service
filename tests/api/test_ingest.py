import pytest
import json
import uuid
import hmac
import hashlib
from fastapi.testclient import TestClient

from app.api.main import app
from app.core.config import settings
from app.core.security import generate_signature


client = TestClient(app)


def test_ingest_webhook():
    """Test ingesting a webhook payload."""
    # First create a subscription
    subscription_response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/test-webhook",
            "secret": None,
            "event_types": None
        },
    )
    
    assert subscription_response.status_code == 200
    subscription_id = subscription_response.json()["id"]
    
    # Then send a webhook payload to the subscription
    payload = {
        "event": "test_event",
        "data": {
            "id": "123",
            "name": "Test Webhook"
        }
    }
    
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{subscription_id}",
        json=payload,
    )
    
    # Check the response
    assert response.status_code == 202
    data = response.json()
    assert data["subscription_id"] == subscription_id
    assert data["payload"] == payload
    assert data["status"] == "pending"
    assert data["attempt_count"] == 0
    assert "id" in data


def test_ingest_webhook_with_signature_verification():
    """Test ingesting a webhook with signature verification."""
    # Create a subscription with a secret
    secret = "my-webhook-secret"
    subscription_response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/test-signature",
            "secret": secret,
            "event_types": None
        },
    )
    
    assert subscription_response.status_code == 200
    subscription_id = subscription_response.json()["id"]
    
    # Prepare payload
    payload = {
        "event": "test_event",
        "data": {
            "id": "123",
            "name": "Test Webhook with Signature"
        }
    }
    payload_bytes = json.dumps(payload).encode()
    
    # Generate valid signature
    valid_signature = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Send webhook with valid signature
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{subscription_id}",
        json=payload,
        headers={"X-Webhook-Signature": valid_signature}
    )
    
    assert response.status_code == 202
    
    # Send webhook with invalid signature
    invalid_signature = "invalid-signature"
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{subscription_id}",
        json=payload,
        headers={"X-Webhook-Signature": invalid_signature}
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_ingest_webhook_with_event_filtering():
    """Test ingesting a webhook with event type filtering."""
    # Create a subscription with event types
    event_types = ["order.created", "user.updated"]
    subscription_response = client.post(
        f"{settings.API_V1_STR}/subscriptions/",
        json={
            "target_url": "https://webhook.site/test-events",
            "secret": None,
            "event_types": event_types
        },
    )
    
    assert subscription_response.status_code == 200
    subscription_id = subscription_response.json()["id"]
    
    # Prepare payload
    payload = {"data": "test"}
    
    # Send webhook with matching event type
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{subscription_id}",
        json=payload,
        headers={"X-Event-Type": "order.created"}
    )
    
    assert response.status_code == 202
    
    # Send webhook with non-matching event type
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{subscription_id}",
        json=payload,
        headers={"X-Event-Type": "order.deleted"}
    )
    
    assert response.status_code == 200
    assert response.json()["message"].startswith("Ignored event type")


def test_ingest_invalid_subscription():
    """Test ingesting a webhook for a non-existent subscription."""
    random_uuid = str(uuid.uuid4())
    response = client.post(
        f"{settings.API_V1_STR}/ingest/{random_uuid}",
        json={"test": "data"},
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Subscription not found"