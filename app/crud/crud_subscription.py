from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from uuid import UUID
from datetime import datetime

from app.db.models.subscription import Subscription
from app.api.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


def create(db: Session, *, obj_in: SubscriptionCreate) -> Subscription:
    """Create a new subscription in the database."""
    db_obj = Subscription(
        target_url=obj_in.target_url,
        secret=obj_in.secret,
        event_types=obj_in.event_types,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get(db: Session, id: UUID) -> Optional[Subscription]:
    """Get a subscription by ID."""
    return db.query(Subscription).filter(Subscription.id == id).first()


def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Subscription]:
    """Get all subscriptions with pagination."""
    return db.query(Subscription).offset(skip).limit(limit).all()


def update(
    db: Session, *, db_obj: Subscription, obj_in: Union[SubscriptionUpdate, Dict[str, Any]]
) -> Subscription:
    """Update a subscription."""
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
    
    for field in update_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])
    
    db_obj.updated_at = datetime.utcnow()
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def remove(db: Session, *, id: UUID) -> Subscription:
    """Remove a subscription."""
    obj = db.query(Subscription).get(id)
    db.delete(obj)
    db.commit()
    return obj


def get_subscription_with_event_type(db: Session, subscription_id: UUID, event_type: str) -> Optional[Subscription]:
    """
    Get a subscription by ID but only if it includes the given event type or has no event_types list.
    
    This performs the event type filtering at the database level for efficiency.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to find
        event_type: Event type to check for in the subscription's event_types list
        
    Returns:
        The subscription if it exists and includes the event type, None otherwise
    """
    # The query checks one of these conditions:
    # 1. The subscription's event_types is NULL (means it accepts all event types)
    # 2. The subscription's event_types contains the given event type
    return db.query(Subscription).filter(
        Subscription.id == subscription_id,
        or_(
            Subscription.event_types.is_(None),  # NULL event_types means accept all
            Subscription.event_types.any(event_type)  # PostgreSQL's ANY operator for arrays
        )
    ).first()


def check_exists(db: Session, subscription_id: UUID) -> bool:
    """
    Efficiently check if a subscription exists by ID.
    
    Args:
        db: Database session
        subscription_id: ID of the subscription to find
        
    Returns:
        True if the subscription exists, False otherwise
    """
    # Use EXISTS and count only to 1 for efficiency
    return db.query(
        db.query(Subscription).filter(Subscription.id == subscription_id).exists()
    ).scalar()