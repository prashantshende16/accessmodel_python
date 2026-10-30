import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project
from ...models.issue import Issue, ErrorEvent
from ...models.uptime import UptimeCheck, Incident
from ..deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/overview")
def get_dashboard_overview(
    organization_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get user projects
    proj_query = db.query(Project).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(OrganizationMembership.user_id == user.id)

    if organization_id:
        proj_query = proj_query.filter(Project.organization_id == organization_id)

    projects = proj_query.all()
    project_ids = [p.id for p in projects]

    if not project_ids:
        return {
            "total_projects": 0,
            "total_issues": 0,
            "unresolved_issues": 0,
            "total_events": 0,
            "uptime_services": 0,
            "active_incidents": 0,
            "recent_issues": [],
            "recent_incidents": [],
            "projects_summary": []
        }

    total_issues = db.query(Issue).filter(Issue.project_id.in_(project_ids)).count()
    unresolved_issues = db.query(Issue).filter(Issue.project_id.in_(project_ids), Issue.status == "unresolved").count()
    total_events = db.query(func.sum(Issue.event_count)).filter(Issue.project_id.in_(project_ids)).scalar() or 0

    uptime_services = db.query(UptimeCheck).filter(UptimeCheck.project_id.in_(project_ids)).count()
    active_incidents = db.query(Incident).join(UptimeCheck, UptimeCheck.id == Incident.check_id).filter(
        UptimeCheck.project_id.in_(project_ids),
        Incident.status == "ongoing"
    ).count()

    recent_issues = db.query(Issue).filter(Issue.project_id.in_(project_ids)).order_by(desc(Issue.last_seen)).limit(5).all()
    recent_incidents = db.query(Incident).join(UptimeCheck, UptimeCheck.id == Incident.check_id).filter(
        UptimeCheck.project_id.in_(project_ids)
    ).order_by(desc(Incident.started_at)).limit(5).all()

    projects_summary = []
    for p in projects:
        issue_count = db.query(Issue).filter(Issue.project_id == p.id, Issue.status == "unresolved").count()
        projects_summary.append({
            "id": p.id,
            "name": p.name,
            "platform": p.platform,
            "environment": p.environment,
            "status": p.status,
            "unresolved_issues": issue_count,
            "last_event_at": p.last_event_at
        })

    return {
        "total_projects": len(projects),
        "total_issues": total_issues,
        "unresolved_issues": unresolved_issues,
        "total_events": total_events,
        "uptime_services": uptime_services,
        "active_incidents": active_incidents,
        "recent_issues": [
            {
                "id": i.id,
                "project_id": i.project_id,
                "project_name": i.project_name,
                "title": i.title,
                "exception_type": i.exception_type,
                "environment": i.environment,
                "severity": i.severity,
                "status": i.status,
                "event_count": i.event_count,
                "last_seen": i.last_seen
            }
            for i in recent_issues
        ],
        "recent_incidents": [
            {
                "id": inc.id,
                "check_name": inc.check.name,
                "url": inc.check.url,
                "message": inc.message,
                "status": inc.status,
                "started_at": inc.started_at,
                "resolved_at": inc.resolved_at
            }
            for inc in recent_incidents
        ],
        "projects_summary": projects_summary
    }

