import datetime
from typing import Optional, List
from pydantic import BaseModel

class ProjectCredentialResponse(BaseModel):
    id: int
    client_key: str
    is_active: bool

    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    name: str
    platform: str = "react"
    environment: str = "production"
    description: Optional[str] = ""

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[str] = None
    environment: Optional[str] = None
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    slug: str
    platform: str
    environment: str
    description: Optional[str]
    status: str
    last_event_at: Optional[datetime.datetime]
    created_at: datetime.datetime
    credentials: List[ProjectCredentialResponse] = []

    class Config:
        from_attributes = True
