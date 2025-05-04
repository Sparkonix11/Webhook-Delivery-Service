from typing import Generic, TypeVar, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from datetime import datetime
from uuid import UUID

T = TypeVar('T')


class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response model"""
    items: List[T]
    total: int
    page: int
    size: int


class BaseResponse(BaseModel):
    """Base response model that includes timestamps and UUID"""
    id: UUID
    created_at: datetime
    
    class Config:
        orm_mode = True


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str