from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum
from datetime import datetime

from app.db.base import Base


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DeliveryTask(Base):
    __tablename__ = "delivery_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    payload = Column(JSONB, nullable=False)
    event_type = Column(String, nullable=True)
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)  # Default max retries as per SRS
    next_attempt_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add indexes and constraints
    __table_args__ = (
        Index('ix_delivery_tasks_subscription_id', subscription_id),
        Index('ix_delivery_tasks_status', status),
        Index('ix_delivery_tasks_created_at', created_at),
        Index('ix_delivery_tasks_next_attempt_at', next_attempt_at),
    )