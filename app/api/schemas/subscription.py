from typing import Optional, List
from pydantic import BaseModel, HttpUrl, validator, Field
from datetime import datetime
from uuid import UUID

from app.api.schemas.common import BaseResponse


class SubscriptionBase(BaseModel):
    """Base subscription schema with shared attributes"""
    target_url: HttpUrl
    event_types: Optional[List[str]] = None

    @validator('target_url')
    def convert_url_to_string(cls, v):
        return str(v)


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a new subscription"""
    secret: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription"""
    target_url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    event_types: Optional[List[str]] = None

    @validator('target_url')
    def convert_url_to_string(cls, v):
        if v is not None:
            return str(v)
        return v


class SubscriptionInDBBase(BaseResponse, SubscriptionBase):
    """Base schema for subscription in DB"""
    updated_at: datetime


class Subscription(SubscriptionInDBBase):
    """Schema for subscription response"""
    # Include a masked version of the secret that only shows the first 4 chars
    masked_secret: Optional[str] = None
    
    @classmethod
    def from_orm(cls, obj):
        # Create the Pydantic model from ORM model
        result = super().from_orm(obj)
        
        # Mask the secret if it exists
        if hasattr(obj, 'secret') and obj.secret:
            prefix = obj.secret[:4] if len(obj.secret) > 4 else obj.secret
            result.masked_secret = f"{prefix}{'*' * 8}"
        else:
            result.masked_secret = None
            
        return result
    
    class Config:
        orm_mode = True
        # Exclude the original secret field
        exclude = {"secret"}