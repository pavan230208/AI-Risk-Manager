import os
import sys
import pandas as pd
import json

# Setup paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer
from app.policy.engine import PolicyEngine

def run_demo():
    print("============================================================")
    print("PHASE 9 END-TO-END DEMONSTRATION")
    print("============================================================")
    
    # 1. Initialize Engines
    ml_engine = MLRiskEngine()
    rule_engine = DeterministicRuleEngine()
    scorer = RiskScorer()
    policy_engine = PolicyEngine()
    
    # 2. Define Test Cases (Raw Transactions)
    test_cases = [
        {
            "description": "1. Legitimate / SAFE transaction",
            "data": pd.DataFrame([{
                "timestamp": "2026-08-25T10:00:00Z",
                "user_id": "U001",
                "merchant_id": "M001",
                "amount": 25.0,
                "device_id": "D001",
                "location": "LOC1"
            }])
        },
        {
            "description": "2. Suspicious / MEDIUM transaction (Velocity Spike)",
            "data": pd.DataFrame([{
                "timestamp": "2026-08-25T10:00:00Z",
                "user_id": "U002",
                "merchant_id": "M002",
                "amount": 40.0,
                "device_id": "D002",
                "location": "LOC2"
            }])
        },
        {
            "description": "3. HIGH-risk transaction requiring review (New Device + High Amount)",
            "data": pd.DataFrame([{
                "timestamp": "2026-08-25T10:00:00Z",
                "user_id": "U003",
                "merchant_id": "M003",
                "amount": 850.0,
                "device_id": "D003",
                "location": "LOC3"
            }])
        },
        {
            "description": "4. CRITICAL transaction requiring strongest protection (Extreme Amount)",
            "data": pd.DataFrame([{
                "timestamp": "2026-08-25T10:00:00Z",
                "user_id": "U004",
                "merchant_id": "M004",
                "amount": 15000.0,
                "device_id": "D004",
                "location": "LOC4"
            }])
        },
        {
            "description": "5. Invalid/missing-risk input triggering fail-safe behavior",
            "data": None
        }
    ]
    
    # Simulate feature context for the demonstration
    mock_historical_context = {
        "U001": {"velocity_1h": 1, "is_new_device": 0, "amount_deviation": 1.0},
        "U002": {"velocity_1h": 12, "is_new_device": 0, "amount_deviation": 1.5},
        "U003": {"velocity_1h": 2, "is_new_device": 1, "amount_deviation": 3.0},
        "U004": {"velocity_1h": 1, "is_new_device": 0, "amount_deviation": 15.0}
    }
    
    for case in test_cases:
        print(f"\n--- {case['description']} ---")
        
        if case["data"] is None:
            # Trigger Fail-safe
            action = policy_engine.evaluate_action(None)
            print("Policy Decision:", action.action_type)
            print("Authorization State:", action.authorization_state)
            print("Human Approval Required:", action.requires_human_approval)
            print("Reason:", action.reason)
            continue
            
        df = case["data"]
        user_id = df.iloc[0]["user_id"]
        features = mock_historical_context[user_id]
        
        # Combine into df_with_features for ML Engine
        df_with_features = df.copy()
        for k, v in features.items():
            df_with_features[k] = v
            
        # We need to fill all expected columns for ML Engine
        expected_cols = ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']
        for col in expected_cols:
            if col not in df_with_features.columns:
                df_with_features[col] = 0.0 # Mock default
        
        # 1. ML Prediction
        ml_result = ml_engine.predict(df_with_features)
        print(f"ML Probability: {ml_result.get('probability', 0.0):.4f}")
        
        # 2. Rule Engine
        tx_dict = df.iloc[0].to_dict()
        rule_signals = rule_engine.evaluate(tx_dict, features)
        print(f"Rule Signals Triggered: {[s.rule_name for s in rule_signals]}")
        
        # 3. Risk Scorer
        score_result = scorer.calculate_score(ml_result, rule_signals)
        print(f"Risk Score: {score_result.final_score}/100")
        print(f"Risk Level: {score_result.risk_level}")
        
        # 4. Policy Engine
        action = policy_engine.evaluate_action(score_result)
        print(f"Policy Decision: {action.action_type}")
        print(f"Authorization State: {action.authorization_state}")
        print(f"Human Approval Required: {action.requires_human_approval}")
        print(f"Policy Reason: {action.reason}")

if __name__ == "__main__":
    run_demo()
