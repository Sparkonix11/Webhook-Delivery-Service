from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class WebhookPayload(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    subscription_id: Optional[str] = None 