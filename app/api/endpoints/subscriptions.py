from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID
import hashlib
import time

from app.db.base import get_db
from app.api.schemas import (
    Subscription, SubscriptionCreate, SubscriptionUpdate, 
    MessageResponse, PaginatedResponse, DeliveryLog
)
from app.crud import crud_subscription
from app.crud import crud_delivery
from app.services import cache
from app.services.cache import redis_client
from app.core.config import settings

router = APIRouter()


def check_subscription_rate_limit(request: Request):
    """
    Stricter rate limiting for subscription creation to prevent abuse.
    Uses a separate rate limiter with stricter limits than the general middleware.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
        
    # Get client identifier (IP address, or X-Forwarded-For if available)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    
    # Specific rate limit for subscription creation (5 per minute)
    limit = 5
    window = 60
    
    # Create a key specific to subscription creation
    rate_limit_key = f"{settings.RATE_LIMIT_REDIS_PREFIX}sub_create:{client_ip}"
    
    # Use Redis pipeline for atomic operations
    current_time = int(time.time())
    pipe = redis_client.pipeline()
    pipe.get(rate_limit_key)
    pipe.incr(rate_limit_key)
    pipe.expire(rate_limit_key, window)
    current_count, _, _ = pipe.execute()
    
    # If key didn't exist, current_count will be None
    current_count = int(current_count) if current_count else 0
    
    if current_count >= limit:
        retry_after = window - (current_time % window)
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "Rate limit exceeded for subscription creation",
                "limit": limit,
                "window": f"{window} seconds",
                "retry_after": retry_after
            }
        )


@router.post("/", response_model=Subscription, dependencies=[Depends(check_subscription_rate_limit)])
def create_subscription(
    subscription_in: SubscriptionCreate, 
    db: Session = Depends(get_db)
):
    """
    Create a new webhook subscription.
    """
    subscription = crud_subscription.create(db, obj_in=subscription_in)
    
    # Cache the subscription data
    cache.cache_subscription(subscription.id, {
        "id": str(subscription.id),
        "target_url": str(subscription.target_url),
        "secret": subscription.secret,
        "event_types": subscription.event_types
    })
    
    return subscription


@router.get("/", response_model=List[Subscription])
def get_subscriptions(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve all webhook subscriptions with pagination.
    """
    subscriptions = crud_subscription.get_all(db, skip=skip, limit=limit)
    return subscriptions


@router.get("/{subscription_id}", response_model=Subscription)
def get_subscription(
    subscription_id: UUID = Path(..., description="The ID of the subscription to get"),
    db: Session = Depends(get_db)
):
    """
    Get a specific webhook subscription by ID.
    """
    subscription = crud_subscription.get(db, id=subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.put("/{subscription_id}", response_model=Subscription)
def update_subscription(
    subscription_in: SubscriptionUpdate,
    subscription_id: UUID = Path(..., description="The ID of the subscription to update"),
    db: Session = Depends(get_db)
):
    """
    Update a webhook subscription.
    """
    subscription = crud_subscription.get(db, id=subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    updated_subscription = crud_subscription.update(
        db, db_obj=subscription, obj_in=subscription_in
    )
    
    # Invalidate the cache
    cache.invalidate_subscription_cache(subscription_id)
    
    return updated_subscription


@router.delete("/{subscription_id}", response_model=MessageResponse)
def delete_subscription(
    subscription_id: UUID = Path(..., description="The ID of the subscription to delete"),
    db: Session = Depends(get_db)
):
    """
    Delete a webhook subscription.
    """
    subscription = crud_subscription.get(db, id=subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    crud_subscription.remove(db, id=subscription_id)
    
    # Invalidate the cache
    cache.invalidate_subscription_cache(subscription_id)
    
    return {"message": "Subscription deleted successfully"}


@router.get("/{subscription_id}/deliveries", response_model=List[DeliveryLog])
def get_subscription_deliveries(
    subscription_id: UUID = Path(..., description="The ID of the subscription"),
    limit: int = Query(20, description="Number of delivery logs to return"),
    db: Session = Depends(get_db)
):
    """
    Get recent delivery logs for a specific subscription.
    """
    # Check if subscription exists
    subscription = crud_subscription.get(db, id=subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Get delivery logs
    delivery_logs = crud_delivery.get_subscription_logs(
        db, subscription_id=subscription_id, limit=limit
    )
    
    return delivery_logs