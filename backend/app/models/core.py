from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="VIEWER")  # ADMIN, RISK_ANALYST, VIEWER
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentPermission(Base):
    __tablename__ = "agent_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    agent_name = Column(String, unique=True, index=True, nullable=False)
    permissions = Column(String, nullable=False)  # JSON string of allowed actions
    created_at = Column(DateTime, default=datetime.utcnow)
