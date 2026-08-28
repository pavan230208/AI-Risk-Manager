from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, index=True) # transaction_id
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True, nullable=True) # Initially nullable for backward compatibility
    user_id = Column(String, index=True, nullable=False)
    merchant_id = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    payment_method = Column(String, nullable=False)
    device_id = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, default="PENDING")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class TransactionFeature(Base):
    __tablename__ = "transaction_features"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), unique=True, index=True, nullable=False)
    features = Column(JSON, nullable=False) # Extracted features
    feature_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskScore(Base):
    __tablename__ = "risk_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=False)
    score = Column(Float, nullable=False)
    probability = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    model_version = Column(String, nullable=False)
    rule_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
