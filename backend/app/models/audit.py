from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Event(Base):
    __tablename__ = "events"
    
    id = Column(String, primary_key=True, index=True) # event_id
    event_type = Column(String, index=True, nullable=False)
    source = Column(String, nullable=False)
    entity_id = Column(String, index=True, nullable=False)
    payload = Column(JSON, nullable=False)
    correlation_id = Column(String, index=True, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    context = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String, index=True, nullable=False) # SYSTEM_HEALTH, MODEL_DRIFT, RISK_SPIKE
    severity = Column(String, nullable=False) # INFO, WARNING, HIGH, CRITICAL
    message = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    status = Column(String, default="UNREAD")
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemHealth(Base):
    __tablename__ = "system_health"
    
    id = Column(Integer, primary_key=True, index=True)
    component = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False) # HEALTHY, DEGRADED, FAILED
    latency_ms = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AgentStatus(Base):
    __tablename__ = "agent_status"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, nullable=False) # ONLINE, OFFLINE, ERROR
    last_heartbeat = Column(DateTime, nullable=False)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String, nullable=False)
    message = Column(String, nullable=False)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
