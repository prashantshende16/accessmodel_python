import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class StackFrameSchema(BaseModel):
    filename: Optional[str] = "unknown"
    function: Optional[str] = "anonymous"
    lineno: Optional[int] = 0
    colno: Optional[int] = 0
    in_app: Optional[bool] = True
    code: Optional[str] = None

class ExceptionDetailSchema(BaseModel):
    type: str = "Error"
    message: str = "An unknown error occurred"
    stacktrace: Optional[List[StackFrameSchema]] = []

class BreadcrumbSchema(BaseModel):
    timestamp: Optional[str] = None
    category: Optional[str] = "ui"
    message: str
    level: Optional[str] = "info"

class EventIngestSchema(BaseModel):
    client_key: Optional[str] = None
    exception: ExceptionDetailSchema
    environment: Optional[str] = "production"
    release: Optional[str] = "1.0.0"
    level: Optional[str] = "error"  # critical, error, warning, info
    request: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    breadcrumbs: Optional[List[BreadcrumbSchema]] = []
    tags: Optional[Dict[str, Any]] = {}
    timestamp: Optional[str] = None

class EventResponse(BaseModel):
    event_id: str
    issue_id: int
    status: str = "received"
