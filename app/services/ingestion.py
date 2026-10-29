import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.project import Project, ProjectCredential
from ..models.issue import Issue, ErrorEvent
from ..models.alert import AlertRule, AlertDelivery
from ..schemas.event import EventIngestSchema
from .grouping import compute_issue_fingerprint, redact_sensitive_data

def ingest_error_event(db: Session, payload: EventIngestSchema, key_from_header: str = None) -> ErrorEvent:
    # 1. Authenticate client key
    client_key = key_from_header or payload.client_key
    if not client_key:
        raise HTTPException(status_code=401, detail="Missing ErrorWatch client key (X-ErrorWatch-Key header or client_key payload)")

    cred = db.query(ProjectCredential).filter(
        ProjectCredential.client_key == client_key,
        ProjectCredential.is_active == True
    ).first()

    if not cred:
        raise HTTPException(status_code=401, detail="Invalid or inactive ErrorWatch client key")

    project = cred.project

    # Update project status to connected and timestamp
    project.status = "connected"
    project.last_event_at = datetime.datetime.utcnow()

    # 2. Compute fingerprint
    fingerprint = compute_issue_fingerprint(project.id, payload.exception)
    env = payload.environment or project.environment or "production"

    # 3. Find or create issue
    issue = db.query(Issue).filter(
        Issue.project_id == project.id,
        Issue.fingerprint == fingerprint,
        Issue.environment == env
    ).first()

    is_new_issue = False
    now = datetime.datetime.utcnow()

    if not issue:
        is_new_issue = True
        issue = Issue(
            project_id=project.id,
            fingerprint=fingerprint,
            title=f"{payload.exception.type}: {payload.exception.message[:200]}",
            exception_type=payload.exception.type,
            message=payload.exception.message,
            environment=env,
            severity=payload.level or "error",
            status="unresolved",
            event_count=1,
            user_count=1 if payload.user else 0,
            first_seen=now,
            last_seen=now,
        )
        db.add(issue)
        db.flush()
    else:
        issue.event_count += 1
        issue.last_seen = now
        # Re-open if previously marked resolved or in_progress
        if issue.status == "resolved":
            issue.status = "unresolved"

    # 4. Redact sensitive context
    req_context = redact_sensitive_data(payload.request or {})
    user_context = redact_sensitive_data(payload.user or {})
    breadcrumbs = [b.dict() for b in (payload.breadcrumbs or [])]
    stacktrace = [f.dict() for f in (payload.exception.stacktrace or [])]

    # 5. Create event
    event = ErrorEvent(
        issue_id=issue.id,
        project_id=project.id,
        environment=env,
        release=payload.release or "1.0.0",
        exception_type=payload.exception.type,
        message=payload.exception.message,
        stacktrace=stacktrace,
        request_context=req_context,
        user_context=user_context,
        breadcrumbs=breadcrumbs,
        tags=payload.tags or {},
        server_received_at=now,
    )
    db.add(event)

    # 6. Check and trigger alerts
    if is_new_issue:
        rules = db.query(AlertRule).filter(
            AlertRule.project_id == project.id,
            AlertRule.trigger_type == "new_issue",
            AlertRule.is_active == True
        ).all()
        for rule in rules:
            delivery = AlertDelivery(
                rule_id=rule.id,
                title=f"New Issue in {project.name}: {issue.title}",
                message=f"A new {issue.severity} issue was detected in {issue.environment}.\nType: {issue.exception_type}",
                status="delivered",
                payload={"issue_id": issue.id, "environment": issue.environment}
            )
            db.add(delivery)

    db.commit()
    db.refresh(event)
    return event
