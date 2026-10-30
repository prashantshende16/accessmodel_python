import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...models.user import User, OrganizationMembership
from ...models.project import Project
from ...models.alert import AlertRule, AlertDelivery
from ...schemas.alert import AlertRuleCreate, AlertRuleResponse, AlertDeliveryResponse
from ..deps import get_current_user

router = APIRouter(prefix="/alerts", tags=["Alerts & Notifications"])

@router.get("/rules", response_model=List[AlertRuleResponse])
def list_rules(
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AlertRule).join(Project, Project.id == AlertRule.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(OrganizationMembership.user_id == user.id)

    if project_id:
        query = query.filter(AlertRule.project_id == project_id)

    return query.order_by(AlertRule.created_at.desc()).all()

@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
def create_rule(
    body: AlertRuleCreate,
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

    rule = AlertRule(
        project_id=project.id,
        name=body.name.strip(),
        trigger_type=body.trigger_type,
        channel=body.channel,
        destination=body.destination or "",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule

@router.get("/deliveries", response_model=List[AlertDeliveryResponse])
def list_deliveries(
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AlertDelivery).join(AlertRule, AlertRule.id == AlertDelivery.rule_id).join(
        Project, Project.id == AlertRule.project_id
    ).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        OrganizationMembership.user_id == user.id
    )

    if project_id:
        query = query.filter(Project.id == project_id)

    return query.order_by(AlertDelivery.created_at.desc()).limit(50).all()

@router.post("/rules/{rule_id}/test", response_model=AlertDeliveryResponse)
def test_alert(rule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rule = db.query(AlertRule).join(Project, Project.id == AlertRule.project_id).join(
        OrganizationMembership, OrganizationMembership.organization_id == Project.organization_id
    ).filter(
        AlertRule.id == rule_id,
        OrganizationMembership.user_id == user.id
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    delivery = AlertDelivery(
        rule_id=rule.id,
        title=f"Test Alert: {rule.name}",
        message=f"This is a simulated test notification for trigger '{rule.trigger_type}' on channel '{rule.channel}'.",
        status="delivered",
        payload={"test": True, "timestamp": datetime.datetime.utcnow().isoformat()}
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery

