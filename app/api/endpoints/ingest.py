from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Header, Request, Response
from sqlalchemy.orm import Session
from uuid import UUID
import json
import hmac
import hashlib
import logging

from app.db.base import get_db
from app.api.schemas import DeliveryTaskCreate, DeliveryTask, MessageResponse, DeliveryTaskWithLogs
from app.crud import crud_subscription, crud_delivery
from app.services import cache
from app.workers.tasks import process_webhook_delivery
from app.core.config import settings
from app.api import deps

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_hmac_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of the payload"""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def verify_event_type(event_type: Optional[str], subscription_event_types: Optional[list[str]]) -> bool:
    """Verify if the event type matches the subscription's event types"""
    if not subscription_event_types:  # No event types specified means accept all
        return True
    if not event_type:  # No event type provided but subscription has filters
        return False
    return event_type in subscription_event_types


@router.post("/{subscription_id}", response_model=DeliveryTask, status_code=202,
             responses={200: {"model": MessageResponse, "description": "Event type ignored"}})
async def ingest_webhook(
    request: Request,
    subscription_id: UUID = Path(..., description="The ID of the subscription"),
    x_event_type: Optional[str] = Header(None, description="Optional event type"),
    x_webhook_signature: Optional[str] = Header(None, description="HMAC signature of payload"),
    db: Session = Depends(get_db)
):
    """
    Ingest a webhook payload for delivery.
    
    This endpoint receives a webhook payload and queues it for asynchronous delivery.
    """
    # Check Content-Length header first to avoid DoS attacks
    max_payload_size = getattr(settings, "MAX_WEBHOOK_PAYLOAD_SIZE", 1024 * 1024)  # Default: 1MB
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            if int(content_length) > max_payload_size:
                raise HTTPException(
                    status_code=413,
                    detail=f"Payload too large. Maximum size is {max_payload_size} bytes"
                )
        except ValueError:
            # Invalid content-length header
            logger.warning(f"Invalid content-length header: {content_length}")
    
    # Use streaming approach to read the body efficiently
    body_chunks = []
    total_size = 0
    
    # Stream the request body in small chunks to check size
    async for chunk in request.stream():
        body_chunks.append(chunk)
        total_size += len(chunk)
        
        # Check size as we read chunks
        if total_size > max_payload_size:
            raise HTTPException(
                status_code=413,
                detail=f"Payload too large. Maximum size is {max_payload_size} bytes"
            )
    
    # Combine chunks to get the full payload
    raw_body = b''.join(body_chunks)
    
    # Check if subscription exists, use efficient query with event type filtering
    # in the database query itself when event_type is provided
    if x_event_type:
        subscription = crud_subscription.get_subscription_with_event_type(db, subscription_id, x_event_type)
        if subscription is None:
            # Check if subscription exists at all
            subscription_exists = crud_subscription.check_exists(db, subscription_id)
            if not subscription_exists:
                raise HTTPException(status_code=404, detail="Subscription not found")
            else:
                # Subscription exists but doesn't want this event type
                return MessageResponse(message=f"Ignored event type: {x_event_type}")
    else:
        # No event type specified, just get the subscription
        subscription = crud_subscription.get(db, id=subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Verify payload signature if provided
    if subscription.secret and x_webhook_signature:
        if not verify_hmac_signature(raw_body, x_webhook_signature, subscription.secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    # Get payload from raw body
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Create delivery task
    task_in = DeliveryTaskCreate(
        subscription_id=subscription_id,
        payload=payload,
        event_type=x_event_type
    )
    delivery_task = crud_delivery.create_delivery_task(db, obj_in=task_in)
    
    # Queue the task for processing
    process_webhook_delivery.delay(str(delivery_task.id))
    
    return delivery_task


@router.get("/delivery/{delivery_task_id}", response_model=DeliveryTaskWithLogs)
def get_delivery_status(
    delivery_task_id: UUID = Path(..., description="The ID of the delivery task"),
    db: Session = Depends(get_db)
):
    """
    Get the status and logs of a webhook delivery task.
    """
    # Use a transaction for consistent reads
    with db.begin():
        task = crud_delivery.get_task(db, id=delivery_task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Delivery task not found")
        
        # Fetch logs for the task
        logs = crud_delivery.get_task_logs(db, task_id=delivery_task_id)
    
    # Create a dictionary with all fields needed for DeliveryTaskWithLogs
    task_dict = {
        "id": task.id,
        "created_at": task.created_at,
        "subscription_id": task.subscription_id,
        "payload": task.payload,
        "event_type": task.event_type,
        "status": task.status,
        "attempt_count": task.attempt_count,
        "next_attempt_at": task.next_attempt_at,
        "logs": logs  # Include logs directly in the initial dictionary
    }
    
    # Create the model with all fields at once
    try:
        task_with_logs = DeliveryTaskWithLogs.model_validate(task_dict)
    except Exception as e:
        # Fallback to dict conversion if model_validate fails
        task_with_logs = DeliveryTaskWithLogs(**task_dict)
    
    return task_with_logs