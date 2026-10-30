import datetime
import secrets
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from ..db.base import Base

def generate_client_key() -> str:
    return "ew_client_" + secrets.token_urlsafe(24).replace("-", "").replace("_", "")

def generate_secret_key() -> str:
    return "ew_sec_" + secrets.token_urlsafe(32).replace("-", "").replace("_", "")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    platform = Column(String(50), default="react")  # react, fastapi, node, python, express, flutter, generic
    environment = Column(String(50), default="production")
    description = Column(Text, default="")
    status = Column(String(50), default="waiting_for_first_event")  # not_configured, waiting_for_first_event, connected
    last_event_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    organization = relationship("Organization", back_populates="projects")
    credentials = relationship("ProjectCredential", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    uptime_checks = relationship("UptimeCheck", back_populates="project", cascade="all, delete-orphan")
    alert_rules = relationship("AlertRule", back_populates="project", cascade="all, delete-orphan")

class ProjectCredential(Base):
    __tablename__ = "project_credentials"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    client_key = Column(String(100), unique=True, index=True, default=generate_client_key)
    secret_key = Column(String(100), default=generate_secret_key)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="credentials")

