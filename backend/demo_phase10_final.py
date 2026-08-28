import os
import sys
import uuid
import pandas as pd
from datetime import datetime, timezone, timedelta

# Setup paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.events import bus, EventSchema
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer
from app.policy.engine import PolicyEngine
from app.actions.executor import ActionExecutor
from app.resilience.kill_switch import state as system_state

# --- Mock Handlers ---
ml_engine = MLRiskEngine()
rule_engine = DeterministicRuleEngine()
scorer = RiskScorer()
policy_engine = PolicyEngine()
action_executor = ActionExecutor()

def handle_transaction_received(event):
    tx_df = event["payload"]["df"]
    
    # Mock Features
    user_id = tx_df.iloc[0]["user_id"]
    if user_id == "U_HIGH":
        features = {"velocity_1h": 2, "is_new_device": 1, "amount_deviation": 5.0} # HIGH
    else:
        features = {"velocity_1h": 1, "is_new_device": 0, "amount_deviation": 1.0} # SAFE
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="FeaturesGenerated",
        correlation_id=event["correlation_id"],
        payload={"tx_dict": tx_df.iloc[0].to_dict(), "features": features},
        producer="FeatureEngine"
    ))

def handle_features_generated(event):
    tx_dict = event["payload"]["tx_dict"]
    features = event["payload"]["features"]
    
    df_with_features = pd.DataFrame([tx_dict])
    for k, v in features.items():
        df_with_features[k] = v
        
    for col in ["user_hist_avg_amt", "velocity_24h", "is_new_location"]:
        if col not in df_with_features.columns:
            df_with_features[col] = 0.0
            
    # Risk Analysis (ML + Rules)
    if tx_dict["user_id"] == "U_SAFE":
        ml_result = {"status": "success", "probability": 0.01, "is_risky": False}
    elif tx_dict.get("mock_ml_failure"):
        ml_result = {"status": "fallback", "error": "Model offline"}
    else:
        ml_result = ml_engine.predict(df_with_features)
        
    rule_signals = rule_engine.evaluate(tx_dict, features)
    
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="RiskAnalyzed",
        correlation_id=event["correlation_id"],
        payload={"ml_result": ml_result, "rule_signals": [s.__dict__ for s in rule_signals]},
        producer="RiskEngine"
    ))

def handle_risk_analyzed(event):
    # Skip complex score reconstruction for demo simplicity. Pass directly to Policy.
    # In a real app we'd construct RiskSignal objects. We'll fake RiskScoreResult.
    payload = event["payload"]
    
    score = 0
    risk_level = "SAFE"
    if payload["ml_result"].get("status") == "fallback":
        # Fallback to high score artificially for this demo
        score = 85
        risk_level = "CRITICAL"
    elif payload["ml_result"].get("probability", 0) > 0.5 or payload["rule_signals"]:
        score = 75
        risk_level = "HIGH"
        
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="RiskScored",
        correlation_id=event["correlation_id"],
        payload={"score": score, "level": risk_level},
        producer="RiskScorer"
    ))

def handle_risk_scored(event):
    from app.risk.scorer import RiskScoreResult
    payload = event["payload"]
    score_result = RiskScoreResult(
        final_score=payload["score"], risk_level=payload["level"],
        signals=[], ml_probability=0.0, requires_human_review=(payload["level"] in ["HIGH", "CRITICAL"])
    )
    
    action = policy_engine.evaluate_action(score_result)
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="PolicyEvaluated",
        correlation_id=event["correlation_id"],
        payload={
            "action_type": action.action_type,
            "authorization_state": action.authorization_state,
            "reason": action.reason
        },
        producer="PolicyEngine"
    ))

def handle_policy_evaluated(event):
    payload = event["payload"]
    if payload["authorization_state"] == "PENDING_APPROVAL":
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()), event_type="ApprovalRequested",
            correlation_id=event["correlation_id"], payload=payload, producer="PolicyEngine"
        ))
    else:
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()), event_type="ActionAuthorized",
            correlation_id=event["correlation_id"], payload=payload, producer="PolicyEngine"
        ))

# We use this global to toggle simulation states dynamically in the demo loop
simulate_approval = False
simulate_expiration = False

def handle_approval_requested(event):
    payload = event["payload"]
    print(f"[{event['correlation_id']}] [WARNING] ACTION NOT EXECUTED — HUMAN APPROVAL REQUIRED: {payload['action_type']}")
    if simulate_approval:
        print(f"[{event['correlation_id']}] [USER] HUMAN APPROVAL RECEIVED")
        payload["authorization_state"] = "AUTHORIZED"
        
        if simulate_expiration:
            payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        else:
            payload["expires_at"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()), event_type="ActionAuthorized",
            correlation_id=event["correlation_id"], payload=payload, producer="HumanAnalyst"
        ))
    else:
        # Pass directly to executor to show it rejects PENDING_APPROVAL
        bus.publish(EventSchema(
            event_id=str(uuid.uuid4()), event_type="ActionAuthorized",
            correlation_id=event["correlation_id"], payload=payload, producer="MockPassthrough"
        ))

def handle_action_authorized(event):
    payload = event["payload"]
    payload["action_id"] = event["event_id"]
    payload["correlation_id"] = event["correlation_id"]
    payload["transaction_id"] = "TX-" + event["correlation_id"]
    payload["version"] = "1.0"
    
    success, reason = action_executor.execute(payload)
    if success:
        print(f"[{event['correlation_id']}] [EXECUTE] ACTION EXECUTED: {payload['action_type']} (Reason: {reason})")
    else:
        print(f"[{event['correlation_id']}] [SECURITY REJECT] Executor Rejected: {reason}")
        
    # Trigger duplicate test if requested via global
    if globals().get("simulate_duplicate") and success:
        print(f"[{event['correlation_id']}] [TEST] Firing identical execution payload again...")
        success2, reason2 = action_executor.execute(payload)
        if not success2:
            print(f"[{event['correlation_id']}] [SECURITY REJECT] Executor Rejected Duplicate: {reason2}")

bus.subscribe("TransactionReceived", handle_transaction_received)
bus.subscribe("FeaturesGenerated", handle_features_generated)
bus.subscribe("RiskAnalyzed", handle_risk_analyzed)
bus.subscribe("RiskScored", handle_risk_scored)
bus.subscribe("PolicyEvaluated", handle_policy_evaluated)
bus.subscribe("ApprovalRequested", handle_approval_requested)
bus.subscribe("ActionAuthorized", handle_action_authorized)

def dispatch_scenario(scenario_name, df, **kwargs):
    print(f"\n{scenario_name}")
    print("-" * 60)
    for k, v in kwargs.items():
        globals()[k] = v
        
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="TransactionReceived",
        correlation_id=f"CORR-{uuid.uuid4().hex[:8]}",
        payload={"df": df}, producer="API"
    ))
    
    for k in kwargs.keys():
        globals()[k] = False

def run_all_cases():
    print("============================================================")
    print("FINAL END-TO-END SAFETY DEMONSTRATION")
    print("============================================================")

    safe_df = pd.DataFrame([{"user_id": "U_SAFE", "amount": 25.0}])
    high_df = pd.DataFrame([{"user_id": "U_HIGH", "amount": 800.0}])

    dispatch_scenario("CASE A — SAFE", safe_df)
    dispatch_scenario("CASE B — HIGH RISK (No Approval)", high_df)
    dispatch_scenario("CASE C — HIGH RISK AFTER APPROVAL", high_df, simulate_approval=True)
    dispatch_scenario("CASE D — EXPIRED APPROVAL", high_df, simulate_approval=True, simulate_expiration=True)
    dispatch_scenario("CASE E — DUPLICATE ACTION", safe_df, simulate_duplicate=True)
    
    print("\nCASE F — UNKNOWN EVENT")
    print("-" * 60)
    evt = EventSchema(event_id=str(uuid.uuid4()), event_type="UnknownGhostEvent", correlation_id="c1", payload={}, producer="Test")
    success = bus.publish(evt)
    print(f"[TEST] Publish Success: {success}")
    print(f"[TEST] DLQ Entries Added: {len(bus.dead_letters)}")
    
    print("\nCASE G — KILL SWITCH")
    print("-" * 60)
    system_state.activate_kill_switch("admin", "test")
    # ActionExecutor will block it
    dispatch_scenario("KILL SWITCH ACTIVE", safe_df, simulate_approval=True)
    system_state.deactivate_kill_switch("admin", "test")
    
    print("\nCASE H — ML FAILURE")
    print("-" * 60)
    ml_fail_df = safe_df.copy()
    ml_fail_df["mock_ml_failure"] = True
    dispatch_scenario("ML UNAVAILABLE", ml_fail_df)
    
if __name__ == "__main__":
    run_all_cases()
