from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project
from ...models.uptime import UptimeCheck, UptimeResult, Incident
from ...schemas.uptime import UptimeCheckCreate, UptimeCheckResponse, IncidentResponse
from ...services.uptime import execute_uptime_check
from ..deps import get_current_user

router = APIRouter(prefix="/uptime", tags=["Uptime Monitoring"])

@router.get("/checks", response_model=List[UptimeCheckResponse])
def list_checks(
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(UptimeCheck).join(Project, Project.id == UptimeCheck.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(OrganizationMembership.user_id == user.id)

    if project_id:
        query = query.filter(UptimeCheck.project_id == project_id)

    checks = query.order_by(UptimeCheck.created_at.desc()).all()
    results = []
    for c in checks:
        recent = db.query(UptimeResult).filter(UptimeResult.check_id == c.id).order_by(UptimeResult.checked_at.desc()).limit(10).all()
        active_inc = db.query(Incident).filter(Incident.check_id == c.id, Incident.status == "ongoing").first()
        results.append(UptimeCheckResponse(
            id=c.id,
            project_id=c.project_id,
            name=c.name,
            url=c.url,
            method=c.method,
            interval_seconds=c.interval_seconds,
            expected_status=c.expected_status,
            is_active=c.is_active,
            status=c.status,
            last_check_at=c.last_check_at,
            last_latency_ms=c.last_latency_ms,
            uptime_percentage=c.uptime_percentage,
            created_at=c.created_at,
            recent_results=recent,
            active_incident=active_inc
        ))
    return results

@router.post("/checks", response_model=UptimeCheckResponse, status_code=201)
def create_check(
    body: UptimeCheckCreate,
    project_id: int = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    project = db.query(Project).join(OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id).filter(
        Project.id == project_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    check = UptimeCheck(
        project_id=project.id,
        name=body.name.strip(),
        url=body.url.strip(),
        method=body.method,
        interval_seconds=body.interval_seconds,
        timeout_seconds=body.timeout_seconds,
        expected_status=body.expected_status,
        status="pending",
    )
    db.add(check)
    db.commit()
    db.refresh(check)

    # Immediately execute first check
    execute_uptime_check(db, check)
    db.refresh(check)

    recent = db.query(UptimeResult).filter(UptimeResult.check_id == check.id).order_by(UptimeResult.checked_at.desc()).limit(10).all()
    return UptimeCheckResponse(
        id=check.id,
        project_id=check.project_id,
        name=check.name,
        url=check.url,
        method=check.method,
        interval_seconds=check.interval_seconds,
        expected_status=check.expected_status,
        is_active=check.is_active,
        status=check.status,
        last_check_at=check.last_check_at,
        last_latency_ms=check.last_latency_ms,
        uptime_percentage=check.uptime_percentage,
        created_at=check.created_at,
        recent_results=recent,
        active_incident=None
    )

@router.post("/checks/{check_id}/run", response_model=UptimeCheckResponse)
def run_check_now(check_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check = db.query(UptimeCheck).join(Project, Project.id == UptimeCheck.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        UptimeCheck.id == check_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not check:
        raise HTTPException(status_code=404, detail="Uptime check not found")

    execute_uptime_check(db, check)
    db.refresh(check)

    recent = db.query(UptimeResult).filter(UptimeResult.check_id == check.id).order_by(UptimeResult.checked_at.desc()).limit(10).all()
    active_inc = db.query(Incident).filter(Incident.check_id == check.id, Incident.status == "ongoing").first()
    return UptimeCheckResponse(
        id=check.id,
        project_id=check.project_id,
        name=check.name,
        url=check.url,
        method=check.method,
        interval_seconds=check.interval_seconds,
        expected_status=check.expected_status,
        is_active=check.is_active,
        status=check.status,
        last_check_at=check.last_check_at,
        last_latency_ms=check.last_latency_ms,
        uptime_percentage=check.uptime_percentage,
        created_at=check.created_at,
        recent_results=recent,
        active_incident=active_inc
    )

@router.delete("/checks/{check_id}")
def delete_check(check_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    check = db.query(UptimeCheck).join(Project, Project.id == UptimeCheck.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        UptimeCheck.id == check_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not check:
        raise HTTPException(status_code=404, detail="Uptime check not found")

    db.delete(check)
    db.commit()
    return {"ok": True}

@router.get("/incidents", response_model=List[IncidentResponse])
def list_incidents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Incident).join(UptimeCheck, UptimeCheck.id == Incident.check_id).join(
        Project, Project.id == UptimeCheck.project_id
    ).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        OrganizationMembership.user_id == user.id
    ).order_by(Incident.started_at.desc()).limit(50).all()

