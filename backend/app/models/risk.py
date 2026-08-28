from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class RiskSignal(Base):
    __tablename__ = "risk_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    signal_type = Column(String, nullable=False) # e.g., VELOCITY_ANOMALY
    description = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskCase(Base):
    __tablename__ = "risk_cases"
    
    id = Column(String, primary_key=True, index=True) # case_id
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    evidence = Column(JSON, nullable=True) # AI generated evidence package
    recommended_action = Column(String, nullable=True)
    status = Column(String, default="OPEN") # OPEN, INVESTIGATING, CLOSED_CONFIRMED, CLOSED_FALSE_POSITIVE
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CaseEvent(Base):
    __tablename__ = "case_events"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("risk_cases.id"), index=True, nullable=False)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=False) # Agent name or User ID
    details = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
