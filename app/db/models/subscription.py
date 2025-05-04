from sqlalchemy import Column, Integer, String, DateTime, ARRAY, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime

from app.db.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    target_url = Column(String, nullable=False)
    secret = Column(String, nullable=True)
    event_types = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add indexes and constraints
    __table_args__ = (
        Index('ix_subscriptions_target_url', target_url),
        Index('ix_subscriptions_created_at', created_at),
        UniqueConstraint('id', name='uq_subscriptions_id'),
    )