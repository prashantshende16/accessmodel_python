import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

class AlertRuleCreate(BaseModel):
    name: str
    trigger_type: str = "new_issue"  # new_issue, uptime_failure, error_spike
    channel: str = "in_app"           # in_app, webhook, email
    destination: Optional[str] = ""

class AlertDeliveryResponse(BaseModel):
    id: int
    rule_id: int
    title: str
    message: str
    status: str
    payload: Dict[str, Any] = {}
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AlertRuleResponse(BaseModel):
    id: int
    project_id: int
    name: str
    trigger_type: str
    channel: str
    destination: Optional[str]
    is_active: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

