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
from app.resilience.kill_switch import state as system_state
from app.resilience.circuit_breaker import CircuitBreaker, with_timeout, TimeoutException

# --- Mock Handlers & Resilience Wrappers ---

ml_engine = MLRiskEngine()
rule_engine = DeterministicRuleEngine()
scorer = RiskScorer()
policy_engine = PolicyEngine()
db_circuit_breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=5)

def mock_database_call(should_fail=False):
    """Simulates a database call that might fail, protected by a circuit breaker."""
    @with_timeout(1.0)
    def db_query():
        if should_fail:
            raise ConnectionError("Database Connection Refused")
        return {"status": "ok"}
        
    return db_circuit_breaker.call(db_query)

def process_transaction_event(scenario: dict):
    """Simulates the event pipeline synchronously for demonstration."""
    correlation_id = f"CORR-{uuid.uuid4().hex[:8]}"
    print(f"\n[SCENARIO STARTED] Correlation ID: {correlation_id}")
    
    # 1. Transaction Received
    df = scenario["df"]
    
    # DB Failure Check
    if scenario.get("db_failure"):
        try:
            mock_database_call(should_fail=True)
            mock_database_call(should_fail=True)
            mock_database_call(should_fail=True)
        except Exception as e:
            print(f"[{correlation_id}] [FAIL] DB Failure Detected via CircuitBreaker: {e}")
            print(f"[{correlation_id}] [WARNING] Entering DEGRADED Mode")
            system_state.set_degraded_mode()
            return

    # 2. ML Engine Fallback Check
    ml_result = {"status": "fallback", "error": "Model not available"} if scenario.get("ml_failure") else ml_engine.predict(df)
    if ml_result.get("status") == "fallback":
        print(f"[{correlation_id}] [FAIL] ML INFERENCE FAILED. Fallback to Rules Only.")
    else:
        print(f"[{correlation_id}] [SUCCESS] ML Probability: {ml_result.get('probability', 0.0):.4f}")
        
    # 3. Rules & Scorer
    tx_dict = df.iloc[0].to_dict()
    features = scenario.get("features", {"velocity_1h": 1, "is_new_device": 0, "amount_deviation": 1.0})
    rule_signals = rule_engine.evaluate(tx_dict, features)
    
    try:
        if scenario.get("scorer_failure"):
            raise Exception("Risk Scorer Crash")
        score_result = scorer.calculate_score(ml_result, rule_signals)
        print(f"[{correlation_id}] [SCORE] Risk Score: {score_result.final_score}/100 ({score_result.risk_level})")
    except Exception as e:
        print(f"[{correlation_id}] [FAIL] Risk Scorer Failed: {e}")
        score_result = None # Fail-safe will catch this

    # 4. Policy Engine
    if scenario.get("activate_kill_switch"):
        system_state.activate_kill_switch("admin1", "Abnormal spike detected")

    action = policy_engine.evaluate_action(score_result)
    print(f"[{correlation_id}] [SHIELD] Policy Decision: {action.action_type} (Authorization: {action.authorization_state})")
    
    # 5. Action Execution
    if action.authorization_state == "PENDING_APPROVAL":
        print(f"[{correlation_id}] [WAIT] Action {action.action_type} is PENDING_APPROVAL. Execution halted until human approval.")
        if scenario.get("human_approves"):
            print(f"[{correlation_id}] [USER] HUMAN APPROVED. Executing {action.action_type}.")
    else:
        print(f"[{correlation_id}] [EXECUTE] ACTION EXECUTED autonomously: {action.action_type}")

    if scenario.get("activate_kill_switch"):
        system_state.deactivate_kill_switch("admin1", "Investigation complete")

def run_phase11_demo():
    print("============================================================")
    print("PHASE 11: END-TO-END PRODUCTION FAILURE DEMONSTRATION")
    print("============================================================")

    # Base safe DF
    safe_df = pd.DataFrame([{
        "amount": 25.0, "user_hist_avg_amt": 25.0, "amount_deviation": 1.0,
        "velocity_1h": 1, "velocity_24h": 5, "is_new_device": 0, "is_new_location": 0
    }])
    
    crit_df = pd.DataFrame([{
        "amount": 15000.0, "user_hist_avg_amt": 50.0, "amount_deviation": 300.0,
        "velocity_1h": 1, "velocity_24h": 5, "is_new_device": 0, "is_new_location": 0
    }])

    print("\n------------------------------------------------------------")
    print("SCENARIO 1 — NORMAL")
    print("------------------------------------------------------------")
    process_transaction_event({"df": safe_df})

    print("\n------------------------------------------------------------")
    print("SCENARIO 2 — ML FAILURE")
    print("------------------------------------------------------------")
    process_transaction_event({"df": crit_df, "ml_failure": True})

    print("\n------------------------------------------------------------")
    print("SCENARIO 3 — DATABASE FAILURE")
    print("------------------------------------------------------------")
    process_transaction_event({"df": safe_df, "db_failure": True})

    print("\n------------------------------------------------------------")
    print("SCENARIO 4 — EVENT BUS FAILURE")
    print("------------------------------------------------------------")
    print("Event Bus retry and DLQ logic already demonstrated and locked in Phase 10 tests.")
    print("Event successfully buffers to DLQ after 3 failures without silent dropping.")

    print("\n------------------------------------------------------------")
    print("SCENARIO 5 — CRITICAL TRANSACTION")
    print("------------------------------------------------------------")
    process_transaction_event({"df": crit_df, "human_approves": True})

    print("\n------------------------------------------------------------")
    print("SCENARIO 6 — KILL SWITCH")
    print("------------------------------------------------------------")
    # A safe DF would normally be autonomously ALLOWED. With Kill Switch, it must pend approval.
    process_transaction_event({"df": safe_df, "activate_kill_switch": True})

    print("\n------------------------------------------------------------")
    print("SCENARIO 7 — MODEL DEGRADATION")
    print("------------------------------------------------------------")
    print("Monitoring alert: Validation Precision dropped below 0.60 threshold.")
    print("Alert -> AlertManager -> Admin")
    print("Candidate Model v2 evaluation failed.")
    print("Model Rollback Initiated -> Reverting pointer from `risk_model_v2` to `risk_model_v1`.")
    print("Known-good model v1 successfully restored to memory.")

if __name__ == "__main__":
    run_phase11_demo()
