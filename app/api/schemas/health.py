from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class DependencyStatus(BaseModel):
    status: str
    error: Optional[str] = None
    workers: Optional[List[str]] = None

class HealthResponse(BaseModel):
    service: str
    status: str
    dependencies: Dict[str, DependencyStatus] 