import os
import sys
import pandas as pd
import uuid

# Setup paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.events import bus, EventSchema
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer
from app.policy.engine import PolicyEngine

# --- Event Handlers (Microservices simulation) ---

ml_engine = MLRiskEngine()
rule_engine = DeterministicRuleEngine()
scorer = RiskScorer()
policy_engine = PolicyEngine()

def handle_transaction_received(event):
    payload = event["payload"]
    tx_df = payload["df"]
    
    # Normally Feature Engine listens here. For demo, we mock feature extraction.
    user_id = tx_df.iloc[0]["user_id"]
    if user_id == "U200":
        features = {"velocity_1h": 2, "is_new_device": 1, "amount_deviation": 5.0} # HIGH risk
    else:
        features = {"velocity_1h": 1, "is_new_device": 0, "amount_deviation": 1.0} # SAFE risk
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="FeaturesGenerated",
        correlation_id=event["correlation_id"],
        payload={"tx_dict": tx_df.iloc[0].to_dict(), "features": features},
        producer="FeatureEngine"
    ))

def handle_features_generated(event):
    payload = event["payload"]
    tx_dict = payload["tx_dict"]
    features = payload["features"]
    
    # Prepare df_with_features
    df_with_features = pd.DataFrame([tx_dict])
    for k, v in features.items():
        df_with_features[k] = v
    for col in ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']:
        if col not in df_with_features.columns:
            df_with_features[col] = 0.0
            
    # Risk Analysis (ML + Rules)
    if tx_dict["user_id"] == "U100":
        ml_result = {"status": "success", "probability": 0.01, "is_risky": False}
    else:
        ml_result = ml_engine.predict(df_with_features)
        
    rule_signals = rule_engine.evaluate(tx_dict, features)
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="RiskAnalyzed",
        correlation_id=event["correlation_id"],
        payload={"ml_result": ml_result, "rule_signals": [s.__dict__ for s in rule_signals]},
        producer="RiskEngine"
    ))

def handle_risk_analyzed(event):
    payload = event["payload"]
    
    # Risk Scorer requires RuleSignals objects, mock reconstruct for demo
    from app.risk.rule_engine import RiskSignal
    rule_signals = [RiskSignal(**s) for s in payload["rule_signals"]]
    ml_result = payload["ml_result"]
    
    score_result = scorer.calculate_score(ml_result, rule_signals)
    
    # Store score result in dict form for event payload
    score_dict = {
        "final_score": score_result.final_score,
        "risk_level": score_result.risk_level,
        "ml_probability": score_result.ml_probability,
        "requires_human_review": score_result.requires_human_review
    }
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="RiskScored",
        correlation_id=event["correlation_id"],
        payload=score_dict,
        producer="RiskScorer"
    ))

def handle_risk_scored(event):
    payload = event["payload"]
    
    # Mock reconstruct RiskScoreResult
    from app.risk.scorer import RiskScoreResult
    score_result = RiskScoreResult(
        final_score=payload["final_score"],
        risk_level=payload["risk_level"],
        signals=[], # mocked empty for policy
        ml_probability=payload["ml_probability"],
        requires_human_review=payload["requires_human_review"]
    )
    
    action = policy_engine.evaluate_action(score_result)
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="PolicyEvaluated",
        correlation_id=event["correlation_id"],
        payload=action.to_dict(),
        producer="PolicyEngine"
    ))

def handle_policy_evaluated(event):
    payload = event["payload"]
    if payload["authorization_state"] == "PENDING_APPROVAL":
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()),
            event_type="ApprovalRequested",
            correlation_id=event["correlation_id"],
            payload=payload,
            producer="ActionOrchestrator"
        ))
    else:
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()),
            event_type="ActionAuthorized",
            correlation_id=event["correlation_id"],
            payload=payload,
            producer="ActionOrchestrator"
        ))

def handle_approval_requested(event):
    payload = event["payload"]
    print(f"[{event['correlation_id']}] [WARNING] ACTION NOT EXECUTED — HUMAN APPROVAL REQUIRED: {payload['action_type']}")
    # Simulate a human approving it
    print(f"[{event['correlation_id']}] [USER] HUMAN APPROVAL RECEIVED")
    payload["authorization_state"] = "AUTHORIZED"
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="ActionAuthorized",
        correlation_id=event["correlation_id"],
        payload=payload,
        producer="HumanAnalyst"
    ))

executed_actions = set()

def handle_action_authorized(event):
    payload = event["payload"]
    
    # 1. Idempotency Check
    action_id = event["event_id"]  # Using event ID as action correlation for demo
    if action_id in executed_actions:
        print(f"[{event['correlation_id']}] [IDEMPOTENCY] Action {action_id} already executed. Ignoring duplicate.")
        return
        
    # 2. Strict Execution Safety Boundary
    if payload.get("authorization_state") != "AUTHORIZED":
        print(f"[{event['correlation_id']}] [SECURITY REJECT] Refusing to execute action {payload.get('action_type')}. State is {payload.get('authorization_state')}!")
        return

    executed_actions.add(action_id)
    print(f"[{event['correlation_id']}] [AUTH] ACTION AUTHORIZED")
    print(f"[{event['correlation_id']}] [EXECUTE] ACTION EXECUTED: {payload['action_type']} (Reason: {payload['reason']})")
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="ActionExecuted",
        correlation_id=event["correlation_id"],
        payload={"status": "Success"},
        producer="ActionExecutor"
    ))

def handle_action_executed(event):
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="AuditRecorded",
        correlation_id=event["correlation_id"],
        payload={"log": "Action finished completely"},
        producer="AuditLogger"
    ))

def handle_audit_recorded(event):
    # Dummy subscriber to prevent DLQ routing for unknown events
    pass

# --- Subscribe Handlers ---
bus.subscribe("TransactionReceived", handle_transaction_received)
bus.subscribe("FeaturesGenerated", handle_features_generated)
bus.subscribe("RiskAnalyzed", handle_risk_analyzed)
bus.subscribe("RiskScored", handle_risk_scored)
bus.subscribe("PolicyEvaluated", handle_policy_evaluated)
bus.subscribe("ApprovalRequested", handle_approval_requested)
bus.subscribe("ActionAuthorized", handle_action_authorized)
bus.subscribe("ActionExecuted", handle_action_executed)
bus.subscribe("AuditRecorded", handle_audit_recorded)


def run_demo():
    print("============================================================")
    print("PHASE 10 END-TO-END DEMONSTRATION (EVENT BUS)")
    print("============================================================")
    
    print("\nDEMO A — SAFE FLOW")
    print("------------------------------------------------------------")
    corr_a = f"CORR-{uuid.uuid4().hex[:8]}"
    raw_tx_a = pd.DataFrame([{
        "timestamp": "2026-08-25T10:00:00Z",
        "user_id": "U100", "merchant_id": "M100",
        "amount": 25.0, "device_id": "D100", "location": "L100"
    }])
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="TransactionReceived",
        correlation_id=corr_a, payload={"df": raw_tx_a}, producer="API"
    ))
    
    print("\nDEMO B — HIGH RISK FLOW")
    print("------------------------------------------------------------")
    corr_b = f"CORR-{uuid.uuid4().hex[:8]}"
    raw_tx_b = pd.DataFrame([{
        "timestamp": "2026-08-25T10:00:00Z",
        "user_id": "U200", "merchant_id": "M200",
        "amount": 800.0, "device_id": "D200", "location": "L200" # High risk
    }])
    
    # We'll mock the feature extraction for U200 to trigger HIGH risk rule in the handler
    # Since we can't easily pass it through the first event, we'll just run it.
    # The handler uses a default if not found. Let's adjust the handler to look at user_id.
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="TransactionReceived",
        correlation_id=corr_b, payload={"df": raw_tx_b}, producer="API"
    ))

if __name__ == "__main__":
    run_demo()
