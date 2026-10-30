import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class ErrorEventDetailResponse(BaseModel):
    id: str
    issue_id: int
    environment: str
    release: str
    exception_type: str
    message: str
    stacktrace: List[Dict[str, Any]] = []
    request_context: Dict[str, Any] = {}
    user_context: Dict[str, Any] = {}
    breadcrumbs: List[Dict[str, Any]] = []
    tags: Dict[str, Any] = {}
    server_received_at: datetime.datetime

    class Config:
        from_attributes = True

class IssueResponse(BaseModel):
    id: int
    project_id: int
    project_name: Optional[str] = None
    project_platform: Optional[str] = None
    fingerprint: str
    title: str
    exception_type: str
    message: str
    environment: str
    severity: str
    status: str
    event_count: int
    user_count: int
    first_seen: datetime.datetime
    last_seen: datetime.datetime

    class Config:
        from_attributes = True

class IssueDetailResponse(IssueResponse):
    latest_event: Optional[ErrorEventDetailResponse] = None

class IssueUpdateStatus(BaseModel):
    status: str  # unresolved, in_progress, resolved, ignored

