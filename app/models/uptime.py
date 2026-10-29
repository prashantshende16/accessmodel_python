import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from ..db.base import Base

class UptimeCheck(Base):
    __tablename__ = "uptime_checks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    method = Column(String(10), default="GET")
    interval_seconds = Column(Integer, default=60)
    timeout_seconds = Column(Integer, default=10)
    expected_status = Column(Integer, default=200)
    is_active = Column(Boolean, default=True)
    
    # Live stats
    status = Column(String(50), default="up")  # up, down, degraded, pending
    last_check_at = Column(DateTime, nullable=True)
    last_latency_ms = Column(Float, nullable=True)
    uptime_percentage = Column(Float, default=100.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="uptime_checks")
    results = relationship("UptimeResult", back_populates="check", cascade="all, delete-orphan", order_by="desc(UptimeResult.checked_at)")
    incidents = relationship("Incident", back_populates="check", cascade="all, delete-orphan", order_by="desc(Incident.started_at)")

class UptimeResult(Base):
    __tablename__ = "uptime_results"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("uptime_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=False)
    is_success = Column(Boolean, nullable=False)
    error_message = Column(Text, default="")
    checked_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    check = relationship("UptimeCheck", back_populates="results")

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("uptime_checks.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), default="ongoing")  # ongoing, resolved
    message = Column(Text, nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    check = relationship("UptimeCheck", back_populates="incidents")
