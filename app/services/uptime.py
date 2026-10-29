import datetime
import time
import httpx
from sqlalchemy.orm import Session
from ..models.uptime import UptimeCheck, UptimeResult, Incident
from ..models.alert import AlertRule, AlertDelivery

def execute_uptime_check(db: Session, check: UptimeCheck) -> UptimeResult:
    now = datetime.datetime.utcnow()
    status_code = None
    is_success = False
    error_message = ""
    start_time = time.time()

    try:
        with httpx.Client(timeout=float(check.timeout_seconds), follow_redirects=True) as client:
            resp = client.request(check.method, check.url)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            status_code = resp.status_code
            is_success = (status_code == check.expected_status)
            if not is_success:
                error_message = f"Expected status {check.expected_status}, got {status_code}"
    except httpx.TimeoutException:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        error_message = f"Connection timed out after {check.timeout_seconds} seconds"
    except httpx.ConnectError as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        error_message = f"Failed to establish connection: {str(e)}"
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        error_message = str(e)

    result = UptimeResult(
        check_id=check.id,
        status_code=status_code,
        latency_ms=latency_ms,
        is_success=is_success,
        error_message=error_message,
        checked_at=now,
    )
    db.add(result)

    # Update check status
    check.last_check_at = now
    check.last_latency_ms = latency_ms

    # Compute uptime percentage over last 50 checks
    recent_checks = db.query(UptimeResult).filter(UptimeResult.check_id == check.id).order_by(UptimeResult.checked_at.desc()).limit(50).all()
    if recent_checks:
        total = len(recent_checks) + 1
        successes = sum(1 for r in recent_checks if r.is_success) + (1 if is_success else 0)
        check.uptime_percentage = round((successes / total) * 100, 2)

    # Incident management
    active_incident = db.query(Incident).filter(
        Incident.check_id == check.id,
        Incident.status == "ongoing"
    ).first()

    if not is_success:
        check.status = "down"
        if not active_incident:
            incident = Incident(
                check_id=check.id,
                status="ongoing",
                message=f"Outage detected: {error_message or f'HTTP {status_code}'}",
                started_at=now,
            )
            db.add(incident)

            # Trigger alert
            rules = db.query(AlertRule).filter(
                AlertRule.project_id == check.project_id,
                AlertRule.trigger_type == "uptime_failure",
                AlertRule.is_active == True
            ).all()
            for rule in rules:
                delivery = AlertDelivery(
                    rule_id=rule.id,
                    title=f"Uptime Outage: {check.name} is DOWN",
                    message=f"Check '{check.name}' ({check.url}) failed with error: {error_message or status_code}",
                    status="delivered",
                    payload={"check_id": check.id, "url": check.url}
                )
                db.add(delivery)
    else:
        check.status = "up"
        if active_incident:
            active_incident.status = "resolved"
            active_incident.resolved_at = now

    db.commit()
    db.refresh(result)
    return result
