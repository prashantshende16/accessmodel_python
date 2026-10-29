import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.security import hash_password, verify_password, create_access_token
from ...models.user import User, Organization, OrganizationMembership
from ...schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse)
def register(body: UserRegister, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email is already registered")

    user = User(
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Create default personal organization
    slug = re.sub(r"[^a-z0-9]+", "-", user.name.lower()).strip("-") or "org"
    slug = f"{slug}-{user.id}"
    org = Organization(name=f"{user.name}'s Workspace", slug=slug)
    db.add(org)
    db.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org.id,
        role="Owner",
    )
    db.add(membership)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(body.password, user.password_hash):
        # Also check with trimmed password
        if not (user and verify_password(body.password.strip(), user.password_hash)):
            raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == current_user.id
    ).all()
    
    orgs = []
    for m in memberships:
        orgs.append({
            "id": m.organization.id,
            "name": m.organization.name,
            "slug": m.organization.slug,
            "role": m.role
        })

    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
        },
        "organizations": orgs
    }
