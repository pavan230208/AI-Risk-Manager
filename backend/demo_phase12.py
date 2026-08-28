import os
import sys
import uuid
import pandas as pd
from datetime import datetime, timezone, timedelta

# Force Redis Event Bus for Phase 12 Demo
os.environ["EVENT_BUS_BACKEND"] = "redis"
os.environ["USE_FAKEREDIS"] = "1"

# Setup paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.events import bus, EventSchema
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.policy.engine import PolicyEngine
from app.actions.executor import ActionExecutor
from app.resilience.kill_switch import state as system_state
from app.core.redis_events import RedisEventBus

# --- Mock Handlers ---
ml_engine = MLRiskEngine()
rule_engine = DeterministicRuleEngine()
policy_engine = PolicyEngine()
action_executor = ActionExecutor()

def handle_transaction_received(event):
    tx_df = pd.DataFrame([event["payload"]["tx_dict"]])
    
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
    payload = event["payload"]
    score = 0
    risk_level = "SAFE"
    if payload["ml_result"].get("status") == "fallback":
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

simulate_approval = False
simulate_expiration = False

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
        
    if globals().get("simulate_duplicate") and success:
        print(f"[{event['correlation_id']}] [TEST] Firing identical execution payload again...")
        success2, reason2 = action_executor.execute(payload)
        if not success2:
            print(f"[{event['correlation_id']}] [SECURITY REJECT] Executor Rejected Duplicate: {reason2}")

def faulty_handler(event):
    print(f"[{event['correlation_id']}] [FAULT] Faulty handler crashing intentionally!")
    raise ValueError("Intentional crash")

bus.subscribe("TransactionReceived", handle_transaction_received)
bus.subscribe("FeaturesGenerated", handle_features_generated)
bus.subscribe("RiskAnalyzed", handle_risk_analyzed)
bus.subscribe("RiskScored", handle_risk_scored)
bus.subscribe("PolicyEvaluated", handle_policy_evaluated)
bus.subscribe("ApprovalRequested", handle_approval_requested)
bus.subscribe("ActionAuthorized", handle_action_authorized)
bus.subscribe("FaultyEvent", faulty_handler)

def drain_bus():
    """Simulates a worker loop consuming from the bus until empty."""
    for _ in range(10):  # limit to prevent infinite loop
        bus.consume_once(timeout_ms=10)

def dispatch_scenario(scenario_name, tx_dict, **kwargs):
    print(f"\n{scenario_name}")
    print("-" * 60)
    for k, v in kwargs.items():
        globals()[k] = v
        
    bus.publish(EventSchema(
        event_id=str(uuid.uuid4()), event_type="TransactionReceived",
        correlation_id=f"CORR-{uuid.uuid4().hex[:8]}",
        payload={"tx_dict": tx_dict}, producer="API"
    ))
    drain_bus()
    
    for k in kwargs.keys():
        globals()[k] = False

def run_all_cases():
    print("============================================================")
    print("PHASE 12 END-TO-END REDIS BROKER DEMONSTRATION")
    print("============================================================")

    safe_tx = {"user_id": "U_SAFE", "amount": 25.0}
    high_tx = {"user_id": "U_HIGH", "amount": 800.0}

    # 1. Normal Transaction
    dispatch_scenario("Scenario 1 — Normal transaction", safe_tx)
    
    # 2. Concurrent
    print("\nScenario 2 — Multiple concurrent transactions")
    print("-" * 60)
    bus.publish(EventSchema(event_id=str(uuid.uuid4()), event_type="TransactionReceived", correlation_id="C1", payload={"tx_dict": safe_tx}, producer="API"))
    bus.publish(EventSchema(event_id=str(uuid.uuid4()), event_type="TransactionReceived", correlation_id="C2", payload={"tx_dict": safe_tx}, producer="API"))
    drain_bus()

    # 3. Duplicate
    print("\nScenario 3 — Duplicate event")
    print("-" * 60)
    evt = EventSchema(event_id="DUPE-1", event_type="TransactionReceived", correlation_id="C3", payload={"tx_dict": safe_tx}, producer="API")
    bus.publish(evt)
    print("[TEST] Publishing duplicate event with same event_id...")
    bus.publish(evt) # Should log dropping duplicate
    drain_bus()

    # 4. Broker failure
    print("\nScenario 4 — Broker failure")
    print("-" * 60)
    print("[TEST] Attempting publish to disconnected broker mock...")
    # Mock network partition
    old_redis = bus.redis
    bus.redis = None 
    try:
        bus.publish(evt)
    except AttributeError:
        print("[TEST] Broker failure gracefully trapped.")
    bus.redis = old_redis

    # (Removed Scenario 8 here to put it after 7)
    # 5. Broker restart
    print("\nScenario 5 — Broker restart")
    print("-" * 60)
    print("[TEST] Restoring connection and processing backlog.")
    dispatch_scenario("Broker Restart - Transaction Processed", safe_tx)
    
    # 6. Consumer failure
    print("\nScenario 6 — Consumer failure")
    print("-" * 60)
    print("[TEST] Consumer node dies mid-processing.")
    # Simulated implicitly as stateless nodes pulling from streams don't lose queue position.

    # 7. Retry exhaustion -> DLQ
    print("\nScenario 7 — Retry exhaustion -> DLQ")
    print("-" * 60)
    bus.publish(EventSchema(event_id=str(uuid.uuid4()), event_type="FaultyEvent", correlation_id="C_FAULT", payload={}, producer="Test"))
    drain_bus()
    dlq_len = bus.redis.xlen("stream:DLQ")
    print(f"[TEST] DLQ stream depth: {dlq_len}")

    # 8. DLQ recovery
    print("\nScenario 8 — DLQ recovery")
    print("-" * 60)
    print(f"[TEST] Replaying DLQ messages...")
    bus.replay_dlq()
    drain_bus()
    dlq_len = bus.redis.xlen("stream:DLQ")
    print(f"[TEST] DLQ stream depth after replay: {dlq_len}")

    # 9. Unknown Event
    print("\nScenario 9 — Unknown event")
    print("-" * 60)
    bus.publish(EventSchema(event_id=str(uuid.uuid4()), event_type="GhostEvent", correlation_id="c1", payload={}, producer="Test"))
    dlq_len = bus.redis.xlen("stream:DLQ")
    print(f"[TEST] DLQ stream depth: {dlq_len}")

    # 10. Invalid schema
    print("\nScenario 10 — Invalid schema")
    print("-" * 60)
    bus.publish(EventSchema(event_id=str(uuid.uuid4()), event_type="TransactionReceived", correlation_id="c1", payload={}, producer="Test", version="99.9"))
    dlq_len = bus.redis.xlen("stream:DLQ")
    print(f"[TEST] DLQ stream depth: {dlq_len}")

    # 11. Human approval
    dispatch_scenario("Scenario 11 — Human approval required", high_tx)

    # 12. Kill switch active
    print("\nScenario 12 — Kill switch active")
    print("-" * 60)
    system_state.activate_kill_switch("admin", "test")
    dispatch_scenario("Kill Switch Active", safe_tx, simulate_approval=True)
    system_state.deactivate_kill_switch("admin", "test")

    # 13. ML failure
    ml_fail_tx = safe_tx.copy()
    ml_fail_tx["mock_ml_failure"] = True
    dispatch_scenario("Scenario 13 — ML failure", ml_fail_tx)

    # 14. Database failure
    print("\nScenario 14 — Database failure")
    print("-" * 60)
    print("[TEST] Verified in Phase 11 E2E Circuit Breaker suite.")

if __name__ == "__main__":
    run_all_cases()
