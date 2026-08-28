from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(String, primary_key=True, index=True) # model_id
    version = Column(String, nullable=False)
    algorithm = Column(String, nullable=False)
    feature_version = Column(String, nullable=False)
    training_dataset_version = Column(String, nullable=False)
    threshold = Column(Float, nullable=False)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    status = Column(String, default="CANDIDATE") # CANDIDATE, TESTING, APPROVED, ACTIVE, REJECTED, ROLLED_BACK
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, ForeignKey("model_versions.id"), index=True, nullable=False)
    evaluation_dataset = Column(String, nullable=False)
    metrics = Column(JSON, nullable=False) # Detailed metrics including false positive costs
    confusion_matrix = Column(JSON, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class ModelFeedback(Base):
    __tablename__ = "model_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String, ForeignKey("risk_cases.id"), index=True, nullable=False)
    analyst_label = Column(String, nullable=False) # CONFIRMED_RISK, FALSE_POSITIVE, UNCERTAIN
    analyst_id = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
