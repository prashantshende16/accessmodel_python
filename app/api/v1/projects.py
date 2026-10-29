import re
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project, ProjectCredential
from ...schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from ...schemas.event import EventIngestSchema, ExceptionDetailSchema, StackFrameSchema
from ...services.ingestion import ingest_error_event
from ..deps import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    organization_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        OrganizationMembership.user_id == user.id
    )
    if organization_id:
        query = query.filter(Project.organization_id == organization_id)
    return query.order_by(Project.created_at.desc()).all()

@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreate,
    organization_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user has access to this org
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not membership or membership.role not in ("Owner", "Administrator", "Developer"):
        raise HTTPException(status_code=403, detail="Not authorized to create projects in this organization")

    name = body.name.strip()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
    
    project = Project(
        organization_id=organization_id,
        name=name,
        slug=slug,
        platform=body.platform,
        environment=body.environment,
        description=body.description or "",
        status="waiting_for_first_event",
    )
    db.add(project)
    db.flush()

    # Generate public client key
    cred = ProjectCredential(project_id=project.id)
    db.add(cred)
    db.commit()
    db.refresh(project)
    return project

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        Project.id == project_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/{project_id}/test-event")
def emit_test_event(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Simulates a test exception to verify SDK integration end-to-end."""
    project = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        Project.id == project_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cred = db.query(ProjectCredential).filter(ProjectCredential.project_id == project.id, ProjectCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=400, detail="No active client key for this project")

    # Generate realistic platform test event
    if project.platform == "fastapi" or project.platform == "python":
        test_payload = EventIngestSchema(
            client_key=cred.client_key,
            exception=ExceptionDetailSchema(
                type="ZeroDivisionError",
                message="division by zero in calculate_billing_metrics()",
                stacktrace=[
                    StackFrameSchema(filename="app/services/billing.py", function="calculate_billing_metrics", lineno=142, in_app=True, code="return total / count"),
                    StackFrameSchema(filename="app/api/v1/billing.py", function="get_metrics", lineno=38, in_app=True, code="metrics = calculate_billing_metrics(account_id)"),
                ]
            ),
            environment=project.environment,
            release="1.0.0",
            level="error",
            request={"method": "GET", "url": "http://127.0.0.1:8000/api/v1/billing/metrics", "headers": {"user-agent": "FastAPI-TestClient/0.1"}},
            breadcrumbs=[
                {"category": "auth", "message": "User admin@example.com authenticated", "level": "info"},
                {"category": "db", "message": "Executed SELECT * FROM accounts WHERE id = 1", "level": "info"},
            ],
            tags={"runtime": "Python 3.10", "framework": "FastAPI"}
        )
    else:
        test_payload = EventIngestSchema(
            client_key=cred.client_key,
            exception=ExceptionDetailSchema(
                type="TypeError",
                message="Cannot read properties of undefined (reading 'map')",
                stacktrace=[
                    StackFrameSchema(filename="src/components/UserTable.jsx", function="renderRows", lineno=84, colno=12, in_app=True, code="items.map((item) => <Row key={item.id} />)"),
                    StackFrameSchema(filename="src/pages/Dashboard.jsx", function="Dashboard", lineno=42, colno=8, in_app=True, code="<UserTable items={data.users} />"),
                ]
            ),
            environment=project.environment,
            release="1.0.0",
            level="error",
            request={"method": "GET", "url": "http://localhost:5173/dashboard", "headers": {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}},
            breadcrumbs=[
                {"category": "navigation", "message": "Navigated to /dashboard", "level": "info"},
                {"category": "ui.click", "message": "User clicked Refresh Table button", "level": "info"},
            ],
            tags={"browser": "Chrome 128.0", "os": "macOS"}
        )

    event = ingest_error_event(db, test_payload)
    return {
        "status": "success",
        "message": "Test event received and recorded successfully! Project is now connected.",
        "event_id": event.id,
        "issue_id": event.issue_id,
        "project_status": project.status
    }
