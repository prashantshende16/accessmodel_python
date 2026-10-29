import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from ..db.base import Base

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    trigger_type = Column(String(50), default="new_issue")  # new_issue, uptime_failure, error_spike
    channel = Column(String(50), default="in_app")  # in_app, webhook, email
    destination = Column(String(500), default="")    # webhook URL or email
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="alert_rules")
    deliveries = relationship("AlertDelivery", back_populates="rule", cascade="all, delete-orphan", order_by="desc(AlertDelivery.created_at)")

class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="delivered")  # delivered, failed
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    rule = relationship("AlertRule", back_populates="deliveries")
