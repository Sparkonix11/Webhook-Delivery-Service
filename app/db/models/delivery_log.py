from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from datetime import datetime

from app.db.base import Base


class DeliveryStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"  # Will be retried
    FAILURE = "FAILURE"  # No more retries


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    delivery_task_id = Column(UUID(as_uuid=True), ForeignKey("delivery_tasks.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    target_url = Column(String, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status = Column(Enum(DeliveryStatus), nullable=False)
    status_code = Column(Integer, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Add indexes and constraints
    __table_args__ = (
        Index('ix_delivery_logs_delivery_task_id', delivery_task_id),
        Index('ix_delivery_logs_subscription_id', subscription_id),
        Index('ix_delivery_logs_created_at', created_at),
        Index('ix_delivery_logs_status', status),
    )