from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Policy(Base):
    __tablename__ = "policies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    rules = Column(JSON, nullable=False) # The policy logic/thresholds
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)

class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), index=True, nullable=False)
    version = Column(String, nullable=False)
    rules = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Approval(Base):
    __tablename__ = "approvals"
    
    id = Column(String, primary_key=True, index=True) # approval_id
    case_id = Column(String, ForeignKey("risk_cases.id"), index=True, nullable=False)
    requested_action = Column(String, nullable=False)
    requested_by = Column(String, nullable=False) # Agent name
    reason = Column(String, nullable=False)
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED, EXPIRED
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class Action(Base):
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    action_type = Column(String, nullable=False) # e.g., BLOCK, ALLOW, NOTIFY
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    approval_id = Column(String, ForeignKey("approvals.id"), nullable=True)
    executed_by = Column(String, nullable=False) # Agent name
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

class ActionResult(Base):
    __tablename__ = "action_results"
    
    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(Integer, ForeignKey("actions.id"), unique=True, index=True, nullable=False)
    success = Column(Boolean, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
