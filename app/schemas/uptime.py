import datetime
from typing import Optional, List
from pydantic import BaseModel

class UptimeCheckCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    interval_seconds: int = 60
    timeout_seconds: int = 10
    expected_status: int = 200

class UptimeResultResponse(BaseModel):
    id: int
    status_code: Optional[int]
    latency_ms: float
    is_success: bool
    error_message: Optional[str]
    checked_at: datetime.datetime

    class Config:
        from_attributes = True

class IncidentResponse(BaseModel):
    id: int
    status: str
    message: str
    started_at: datetime.datetime
    resolved_at: Optional[datetime.datetime]

    class Config:
        from_attributes = True

class UptimeCheckResponse(BaseModel):
    id: int
    project_id: int
    name: str
    url: str
    method: str
    interval_seconds: int
    expected_status: int
    is_active: bool
    status: str
    last_check_at: Optional[datetime.datetime]
    last_latency_ms: Optional[float]
    uptime_percentage: float
    created_at: datetime.datetime
    recent_results: List[UptimeResultResponse] = []
    active_incident: Optional[IncidentResponse] = None

    class Config:
        from_attributes = True
