import re
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project, ProjectCredential
from ...schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, TestEventRequest
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

@router.delete("/{project_id}")
def delete_project(project_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        Project.id == project_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True, "message": f"Project '{project.name}' deleted"}

@router.post("/{project_id}/test-event")
def emit_test_event(
    project_id: int,
    req_body: Optional[TestEventRequest] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Simulates a test exception or accepts custom test parameters to verify SDK integration end-to-end."""
    project = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        Project.id == project_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    cred = db.query(ProjectCredential).filter(ProjectCredential.project_id == project.id, ProjectCredential.is_active == True).first()
    if not cred:
        raise HTTPException(status_code=400, detail="No active client key for this project")

    pname_clean = re.sub(r"[^a-zA-Z0-9]+", "", project.name) or "App"
    existing_issue_count = len(project.issues)

    # 1. Custom user-provided test error
    if req_body and (req_body.error_type or req_body.message):
        err_type = req_body.error_type or "Error"
        err_msg = req_body.message or f"Custom test error in {project.name}"
        fn = req_body.filename or f"src/{pname_clean}.js"
        func = req_body.function or "handleAction"
        test_payload = EventIngestSchema(
            client_key=cred.client_key,
            exception=ExceptionDetailSchema(
                type=err_type,
                message=err_msg,
                stacktrace=[
                    StackFrameSchema(filename=fn, function=func, lineno=42, colno=10, in_app=True, code=f"throw new {err_type}('{err_msg}')")
                ]
            ),
            environment=project.environment,
            release="1.0.0",
            level="error",
            request={"method": "GET", "url": f"https://{project.slug}.example.com/test"},
            breadcrumbs=[
                {"category": "test", "message": f"Manual test event initiated for {project.name}", "level": "info"}
            ],
            tags={"project": project.name, "platform": project.platform}
        )
    # 2. Dynamic platform & project-tailored test error
    elif project.platform in ("fastapi", "python"):
        scenarios = [
            (
                "OperationalError",
                f"psycopg2.OperationalError: server closed connection unexpectedly in {project.name}",
                [
                    StackFrameSchema(filename="app/db/session.py", function="get_db", lineno=32, in_app=True, code="conn = pool.get_connection(timeout=5)"),
                    StackFrameSchema(filename=f"app/services/{pname_clean.lower()}_service.py", function="query_records", lineno=78, in_app=True, code="return db.query(Model).filter_by(active=True).all()"),
                ]
            ),
            (
                "KeyError",
                f"KeyError: 'auth_payload' missing required claims in {project.name}",
                [
                    StackFrameSchema(filename="app/core/security.py", function="extract_claims", lineno=54, in_app=True, code="user_id = token_data['auth_payload']['user_id']"),
                    StackFrameSchema(filename=f"app/api/v1/{pname_clean.lower()}.py", function="handle_request", lineno=29, in_app=True, code="claims = extract_claims(authorization)"),
                ]
            ),
            (
                "ZeroDivisionError",
                f"ZeroDivisionError: division by zero in calculate_{pname_clean.lower()}_metrics()",
                [
                    StackFrameSchema(filename="app/services/analytics.py", function="calculate_metrics", lineno=112, in_app=True, code="return total_amount / total_count"),
                    StackFrameSchema(filename=f"app/api/v1/{pname_clean.lower()}.py", function="get_metrics", lineno=45, in_app=True, code="metrics = calculate_metrics(account_id)"),
                ]
            )
        ]
        chosen = scenarios[existing_issue_count % len(scenarios)]
        test_payload = EventIngestSchema(
            client_key=cred.client_key,
            exception=ExceptionDetailSchema(
                type=chosen[0],
                message=chosen[1],
                stacktrace=chosen[2]
            ),
            environment=project.environment,
            release="1.0.0",
            level="error",
            request={"method": "GET", "url": f"http://127.0.0.1:8000/api/v1/{project.slug}", "headers": {"user-agent": "FastAPI-TestClient/0.1"}},
            breadcrumbs=[
                {"category": "auth", "message": "User authenticated", "level": "info"},
                {"category": "db", "message": f"Executing query for {project.name}", "level": "info"},
            ],
            tags={"runtime": "Python 3.10", "framework": "FastAPI", "project": project.name}
        )
    else:
        # React, Node, Web, Flutter, Generic
        scenarios = [
            (
                "AxiosError",
                f"Request failed with status code 502 (Bad Gateway) in {project.name}",
                [
                    StackFrameSchema(filename="src/services/apiClient.js", function="requestWithRetry", lineno=48, colno=14, in_app=True, code="const res = await axios.get(endpoint, config);"),
                    StackFrameSchema(filename=f"src/pages/{pname_clean}Page.jsx", function="loadData", lineno=62, colno=8, in_app=True, code="const data = await apiClient.fetchData();"),
                ]
            ),
            (
                "ChunkLoadError",
                f"Loading chunk for {project.name} failed (missing asset bundle or network timeout)",
                [
                    StackFrameSchema(filename="src/router/AppRoutes.jsx", function="lazyLoadRoute", lineno=31, colno=16, in_app=True, code=f"const Page = React.lazy(() => import('../pages/{pname_clean}'));"),
                ]
            ),
            (
                "TypeError",
                f"Cannot read properties of undefined (reading 'data') in {pname_clean}Container",
                [
                    StackFrameSchema(filename=f"src/components/{pname_clean}View.jsx", function="renderContent", lineno=94, colno=18, in_app=True, code="return items.data.map((item) => <Card key={item.id} />);"),
                    StackFrameSchema(filename=f"src/pages/{pname_clean}Page.jsx", function="PageWrapper", lineno=45, colno=10, in_app=True, code=f"<{pname_clean}View items={{}} />"),
                ]
            ),
            (
                "UnhandledPromiseRejection",
                f"Uncaught (in promise) Failed to execute '{pname_clean}ActionHandler'",
                [
                    StackFrameSchema(filename=f"src/hooks/use{pname_clean}.js", function="executeAction", lineno=58, colno=12, in_app=True, code="await dispatchRemoteAction(actionPayload);"),
                ]
            )
        ]
        chosen = scenarios[existing_issue_count % len(scenarios)]
        test_payload = EventIngestSchema(
            client_key=cred.client_key,
            exception=ExceptionDetailSchema(
                type=chosen[0],
                message=chosen[1],
                stacktrace=chosen[2]
            ),
            environment=project.environment,
            release="1.0.0",
            level="error",
            request={"method": "GET", "url": f"https://{project.slug}.example.com/app", "headers": {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}},
            breadcrumbs=[
                {"category": "navigation", "message": f"Navigated to /{pname_clean.lower()}", "level": "info"},
                {"category": "ui.click", "message": f"User interacted with {project.name}", "level": "info"},
            ],
            tags={"browser": "Chrome 128.0", "os": "macOS", "project": project.name}
        )

    event = ingest_error_event(db, test_payload)
    return {
        "status": "success",
        "message": f"Verified test event '{test_payload.exception.type}' emitted and grouped for {project.name}!",
        "event_id": event.id,
        "issue_id": event.issue_id,
        "project_status": project.status
    }

