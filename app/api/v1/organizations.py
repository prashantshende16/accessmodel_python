import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models.user import User, Organization, OrganizationMembership
from ...schemas.organization import OrganizationCreate, OrganizationResponse
from ..deps import get_current_user

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.get("", response_model=List[OrganizationResponse])
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id
    ).all()
    return [m.organization for m in memberships]

@router.post("", response_model=OrganizationResponse)
def create_organization(body: OrganizationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = body.name.strip()
    slug_base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    slug = f"{slug_base}-{user.id}"
    
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role="Owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(org)
    return org

