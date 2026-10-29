import datetime
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ..db.base import Base

class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint = Column(String(64), nullable=False, index=True)  # SHA-256 grouping hash
    title = Column(String(500), nullable=False)
    exception_type = Column(String(255), nullable=False)
    message = Column(Text, default="")
    environment = Column(String(50), default="production", index=True)
    severity = Column(String(50), default="error")  # critical, error, warning, info
    status = Column(String(50), default="unresolved", index=True)  # unresolved, in_progress, resolved, ignored
    event_count = Column(Integer, default=1)
    user_count = Column(Integer, default=1)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="issues")
    events = relationship("ErrorEvent", back_populates="issue", cascade="all, delete-orphan", order_by="desc(ErrorEvent.server_received_at)")

class ErrorEvent(Base):
    __tablename__ = "error_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    environment = Column(String(50), default="production")
    release = Column(String(100), default="1.0.0")
    exception_type = Column(String(255), nullable=False)
    message = Column(Text, default="")
    
    # Structured context
    stacktrace = Column(JSON, default=list)       # List of frames: { filename, function, lineno, colno, in_app, code }
    request_context = Column(JSON, default=dict)   # { method, url, headers, query_params, ip }
    user_context = Column(JSON, default=dict)      # { id, email, username }
    breadcrumbs = Column(JSON, default=list)       # List of { timestamp, category, message, level }
    tags = Column(JSON, default=dict)              # { browser, os, runtime, etc. }
    
    server_received_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    issue = relationship("Issue", back_populates="events")
