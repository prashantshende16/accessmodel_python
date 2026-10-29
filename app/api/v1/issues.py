from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project
from ...models.issue import Issue, ErrorEvent
from ...schemas.issue import IssueResponse, IssueDetailResponse, IssueUpdateStatus, ErrorEventDetailResponse
from ..deps import get_current_user

router = APIRouter(prefix="/issues", tags=["Issues"])

@router.get("", response_model=List[IssueResponse])
def list_issues(
    project_id: Optional[int] = None,
    environment: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Issue).join(Project, Project.id == Issue.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(OrganizationMembership.user_id == user.id)

    if project_id:
        query = query.filter(Issue.project_id == project_id)
    if environment and environment != "all":
        query = query.filter(Issue.environment == environment)
    if status and status != "all":
        query = query.filter(Issue.status == status)
    if severity and severity != "all":
        query = query.filter(Issue.severity == severity)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(Issue.title.ilike(s), Issue.exception_type.ilike(s), Issue.message.ilike(s)))

    return query.order_by(desc(Issue.last_seen)).limit(100).all()

@router.get("/{issue_id}", response_model=IssueDetailResponse)
def get_issue(issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    issue = db.query(Issue).join(Project, Project.id == Issue.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        Issue.id == issue_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    latest_event = db.query(ErrorEvent).filter(ErrorEvent.issue_id == issue.id).order_by(desc(ErrorEvent.server_received_at)).first()

    return IssueDetailResponse(
        id=issue.id,
        project_id=issue.project_id,
        fingerprint=issue.fingerprint,
        title=issue.title,
        exception_type=issue.exception_type,
        message=issue.message,
        environment=issue.environment,
        severity=issue.severity,
        status=issue.status,
        event_count=issue.event_count,
        user_count=issue.user_count,
        first_seen=issue.first_seen,
        last_seen=issue.last_seen,
        latest_event=latest_event
    )

@router.put("/{issue_id}/status", response_model=IssueResponse)
def update_issue_status(
    issue_id: int,
    body: IssueUpdateStatus,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    issue = db.query(Issue).join(Project, Project.id == Issue.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        Issue.id == issue_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if body.status not in ("unresolved", "in_progress", "resolved", "ignored"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    issue.status = body.status
    db.commit()
    db.refresh(issue)
    return issue

@router.delete("/{issue_id}")
def delete_issue(issue_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    issue = db.query(Issue).join(Project, Project.id == Issue.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        Issue.id == issue_id,
        OrganizationMembership.user_id == user.id
    ).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    db.delete(issue)
    db.commit()
    return {"ok": True}
