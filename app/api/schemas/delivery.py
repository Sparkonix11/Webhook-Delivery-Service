from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
import enum

from app.api.schemas.common import BaseResponse


class DeliveryTaskStatus(str, enum.Enum):
    """Status enum for delivery tasks"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DeliveryLogStatus(str, enum.Enum):
    """Status enum for delivery logs"""
    SUCCESS = "SUCCESS"
    FAILED_ATTEMPT = "FAILED_ATTEMPT"  # Will be retried
    FAILURE = "FAILURE"  # No more retries


class DeliveryTaskCreate(BaseModel):
    """Schema for creating a delivery task"""
    subscription_id: UUID
    payload: Dict[str, Any]
    event_type: Optional[str] = None


class DeliveryTask(BaseResponse):
    """Schema for delivery task response"""
    subscription_id: UUID
    payload: Dict[str, Any]
    event_type: Optional[str]
    status: DeliveryTaskStatus
    attempt_count: int
    next_attempt_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class DeliveryLog(BaseResponse):
    """Schema for delivery log response"""
    delivery_task_id: UUID
    subscription_id: UUID
    target_url: str
    attempt_number: int
    status: DeliveryLogStatus
    status_code: Optional[int]
    error_details: Optional[str]
    
    class Config:
        from_attributes = True


class DeliveryTaskWithLogs(DeliveryTask):
    """Schema for delivery task with logs"""
    logs: List[DeliveryLog]