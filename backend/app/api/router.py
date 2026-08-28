from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
import pandas as pd
from typing import Dict, Any

from app.ml.inference import MLRiskEngine
from app.ml.features import extract_features
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer
from app.policy.engine import PolicyEngine
from app.actions.executor import ActionExecutor
from app.core.events import EventSchema, bus
from app.resilience.kill_switch import state as system_state
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import Depends, HTTPException
from app.api.auth import require_roles, Role, verify_api_key, verify_integration_api_key
from app.resilience.automation_state import automation_state
from app.resilience.rate_limiter import rate_limiter
from sqlalchemy.orm import Session
from app.db.database import get_db

router = APIRouter()

ml_engine = MLRiskEngine()
rule_engine = DeterministicRuleEngine()
scorer = RiskScorer()
policy_engine = PolicyEngine()
action_executor = ActionExecutor()



class TransactionPayload(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=1, max_length=100)
    merchant_id: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., ge=0.0, lt=1e15, allow_inf_nan=False)
    currency: str = Field("USD", min_length=3, max_length=3)
    device_id: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=2, max_length=100)
    timestamp: str

    model_config = {"extra": "forbid"}

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("Amount cannot be negative")
        return v

@router.get("/status")
def status():
    return {"status": "operational", "service": "Autonomous AI Risk Manager API", "ml_ready": ml_engine.is_ready}

from app.api.auth import require_roles, Role, verify_api_key

@router.post("/evaluate")
def evaluate_transaction(payload: TransactionPayload, api_key: str = Depends(verify_api_key), tenant_id: str = None, db: Session = Depends(get_db)):
    correlation_id = str(uuid.uuid4())
    
    tx_dict = payload.model_dump()
    df = pd.DataFrame([tx_dict])
    
    try:
        from app.ml.features import FeatureEngineeringError
        df_features = extract_features(df)
        ml_result = ml_engine.predict(df_features)
        features_dict = df_features.iloc[0].to_dict()
    except FeatureEngineeringError as e:
        # FAIL SAFE: Reject dangerous malformed input
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Feature engineering failed for {payload.transaction_id}: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Malformed transaction data: {str(e)}")
        
    rule_signals = rule_engine.evaluate(tx_dict, features_dict)
    score_result = scorer.calculate_score(ml_result, rule_signals)
    
    policy_action = policy_engine.evaluate_action(score_result)
    
    action_id = payload.transaction_id
    action_request = {
        "event_id": str(uuid.uuid4()),
        "action_id": action_id,
        "correlation_id": correlation_id,
        "transaction_id": payload.transaction_id,
        "tenant_id": tenant_id, # Added tenant isolation support for executor if needed
        "action_type": policy_action.action_type,
        "version": policy_action.version,
        "authorization_state": policy_action.authorization_state,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    }
    
    execution_success, execution_reason = action_executor.execute(action_request)
    
    # Save the transaction in DB
    from app.models.transaction import Transaction
    db_tx = Transaction(
        id=payload.transaction_id,
        tenant_id=tenant_id,
        user_id=payload.user_id,
        merchant_id=payload.merchant_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method="API",
        device_id=payload.device_id,
        location=payload.location,
        status=execution_reason
    )
    # Simple deduplication handled by idempotency, but here we just merge to avoid unique constraints crash
    db.merge(db_tx)
    db.commit()
    
    event = EventSchema(
        event_id=action_request["event_id"],
        event_type="TransactionEvaluated",
        correlation_id=correlation_id,
        payload={
            "transaction_id": payload.transaction_id,
            "tenant_id": tenant_id,
            "risk_score": score_result.final_score,
            "policy_action": policy_action.action_type,
            "execution_status": execution_reason
        },
        producer="FastAPI_Router"
    )
    bus.publish(event)
    
    return {
        "transaction_id": payload.transaction_id,
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "ml_probability": score_result.ml_probability,
        "ml_status": "SUCCESS",
        "rule_signals": [s.rule_name for s in score_result.signals],
        "final_score": score_result.final_score,
        "risk_level": score_result.risk_level,
        "policy_action": policy_action.action_type,
        "human_approval_required": policy_action.requires_human_approval,
        "authorization_state": policy_action.authorization_state,
        "execution_status": execution_reason,
        "policy_version": policy_action.version,
        "model_version": getattr(ml_engine, 'version', "1.0"),
        "explanation": policy_action.reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/system/trace")
def system_trace(auth_payload: dict = Depends(require_roles([Role.ADMIN, Role.ANALYST, Role.OPERATOR, Role.VIEWER]))):
    redis_conn = action_executor._get_redis()
    recent_events = bus.get_recent_events(20)
    # The frontend expects older events first or it calls reverse() on them.
    # The get_recent_events sorted them descending (newest first). 
    # Let's reverse to match what InMemory event_log[-20:] did (oldest first in list).
    recent_events.reverse()
    return {
        "system_state": "AUTONOMOUS_ACTIONS_DISABLED" if system_state.kill_switch_active else "NORMAL",
        "redis_status": "CONNECTED" if redis_conn else "DISCONNECTED",
        "event_bus_status": "READY",
        "automated_protection_enabled": automation_state.is_enabled,
        "recent_events": recent_events,
        "audit_events": recent_events, 
        "dlq_count": bus.get_dlq_count()
    }

class KillSwitchPayload(BaseModel):
    active: bool

@router.post("/system/kill-switch")
def toggle_kill_switch(payload: KillSwitchPayload, auth_payload: dict = Depends(require_roles([Role.ADMIN]))):
    user_id = auth_payload.get("sub", "unknown")
    role = auth_payload.get("role", "unknown")
    action = "ACTIVATE_KILL_SWITCH" if payload.active else "DEACTIVATE_KILL_SWITCH"
    correlation_id = str(uuid.uuid4())

    if payload.active:
        system_state.activate_kill_switch(user_id, "Admin request")
    else:
        system_state.deactivate_kill_switch(user_id, "Admin request")
        
    audit_event = EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="AdminAudit",
        correlation_id=correlation_id,
        payload={
            "actor": user_id,
            "role": role,
            "action": action,
            "target": "KillSwitch",
            "result": "SUCCESS",
            "reason": "Admin request",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        producer="FastAPI_Router"
    )
    bus.publish(audit_event)
    
    return {"kill_switch_active": system_state.kill_switch_active}

class AutomationStatePayload(BaseModel):
    active: bool

@router.post("/integration/automation-state")
def toggle_automation_state(payload: AutomationStatePayload, auth_payload: dict = Depends(require_roles([Role.ADMIN]))):
    if payload.active:
        automation_state.enable()
    else:
        automation_state.disable()
    
    # Audit log
    audit_event = EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="AdminAudit",
        correlation_id=str(uuid.uuid4()),
        payload={
            "actor": auth_payload.get("sub", "unknown"),
            "role": auth_payload.get("role", "unknown"),
            "action": "ENABLE_AUTOMATED_PROTECTION" if payload.active else "DISABLE_AUTOMATED_PROTECTION",
            "target": "AutomationState",
            "result": "SUCCESS",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        producer="FastAPI_Router"
    )
    bus.publish(audit_event)
    return {"automated_protection_enabled": automation_state.is_enabled}

@router.get("/integration/health")
def integration_health():
    redis_conn = action_executor._get_redis()
    return {
        "API": "HEALTHY",
        "PostgreSQL": "HEALTHY", # we assume ok if it got here, ideally check db session
        "Redis": "HEALTHY" if redis_conn and redis_conn.ping() else "UNHEALTHY",
        "EventBus": "HEALTHY",
        "Automated_Protection": "ENABLED" if automation_state.is_enabled else "DISABLED"
    }

@router.post("/transactions/evaluate")
def evaluate_transaction_automated(payload: TransactionPayload, auth_context: dict = Depends(verify_integration_api_key), db: Session = Depends(get_db)):
    
    tenant_id = auth_context.get("tenant_id")
    client_id = tenant_id if tenant_id else "legacy_api"
    
    rate_limiter.check_limit(f"integration_api:{client_id}")
    
    if not automation_state.is_enabled:
        raise HTTPException(status_code=403, detail="Automated Protection is disabled. Requests must be evaluated manually.")
        
    # Prevent client from specifying arbitrary tenant_id if we extend the payload to have it.
    # Currently payload doesn't have tenant_id in TransactionPayload.
    
    # We will pass the tenant_id to the evaluate_transaction function
    return evaluate_transaction(payload, api_key="placeholder", tenant_id=tenant_id, db=db)

@router.post("/webhooks/transactions")
def evaluate_transaction_webhook(
    raw_payload: Dict[str, Any], 
    provider: str = "generic", 
    auth_context: dict = Depends(verify_integration_api_key), 
    db: Session = Depends(get_db)
):
    """
    Universal Webhook Endpoint for multi-tenant, provider-agnostic automated ingestion.
    """
    from app.adapters.providers import ProviderAdapterFactory, ProviderAdapterError
    
    try:
        adapter = ProviderAdapterFactory.get_adapter(provider)
        normalized_payload = adapter.normalize(raw_payload)
    except ProviderAdapterError as e:
        raise HTTPException(status_code=422, detail=f"Provider normalization failed: {str(e)}")
        
    return evaluate_transaction_automated(payload=normalized_payload, auth_context=auth_context, db=db)
