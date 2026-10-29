from typing import List, Optional
from pydantic import BaseModel
from .auth import UserResponse

class OrganizationCreate(BaseModel):
    name: str

class OrganizationMemberResponse(BaseModel):
    id: int
    user_id: int
    role: str
    user: UserResponse

    class Config:
        from_attributes = True

class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True
