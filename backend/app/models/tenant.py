from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, index=True) # e.g. "TENANT_123"
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    api_keys = relationship("APIKey", back_populates="tenant")
    # relationships with transactions could be added later if needed

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, index=True) # e.g. "KEY_123"
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    key_prefix = Column(String, nullable=False, index=True) # e.g. "pk_live_123"
    key_hash = Column(String, nullable=False) # Argon2 or bcrypt hash of the secret
    name = Column(String, nullable=False)
    
    is_active = Column(Boolean, default=True)
    is_revoked = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    
    tenant = relationship("Tenant", back_populates="api_keys")
