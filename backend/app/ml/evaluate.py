import os
import sys
import pandas as pd
import json

# Add backend to path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer

def evaluate_pipeline():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    csv_path = os.path.join(data_dir, "synthetic_transactions.csv")
    
    print("Loading HELD-OUT TEST dataset...")
    df = pd.read_csv(csv_path)
    test_df = df[df['split'] == 'test'].copy()
    
    print(f"Total test samples: {len(test_df)}")
    
    print("Extracting features (identical pipeline)...")
    df_features = extract_features(test_df)
    
    ml_engine = MLRiskEngine()
    rule_engine = DeterministicRuleEngine()
    scorer = RiskScorer()
    
    results = []
    
    for idx, row in df_features.iterrows():
        # ML Inference
        single_tx_df = pd.DataFrame([row])
        ml_result = ml_engine.predict(single_tx_df)
        
        # Rule Engine
        tx_dict = row.to_dict()
        signals = rule_engine.evaluate(tx_dict, tx_dict)
        
        # Scorer
        score_result = scorer.calculate_score(ml_result, signals)
        
        results.append({
            "is_fraud": tx_dict.get("is_fraud", 0),
            "final_score": score_result.final_score,
            "risk_level": score_result.risk_level,
            "ml_risky": ml_result.get("is_risky", False),
            "rule_caught": len(signals) > 0
        })
        
    res_df = pd.DataFrame(results)
    
    # Calculate Metrics
    actual_frauds = res_df[res_df['is_fraud'] == 1]
    actual_legits = res_df[res_df['is_fraud'] == 0]
    
    ml_caught = actual_frauds[actual_frauds['ml_risky'] == True]
    rules_caught = actual_frauds[actual_frauds['rule_caught'] == True]
    
    system_flagged = res_df[res_df['risk_level'].isin(['HIGH', 'CRITICAL'])]
    
    true_positives = len(system_flagged[system_flagged['is_fraud'] == 1])
    false_positives = len(system_flagged[system_flagged['is_fraud'] == 0])
    false_negatives = len(actual_frauds) - true_positives
    
    print("\n--- PHASE 8 EVALUATION RESULTS ---")
    print(f"Total Fraud Cases in Test Set: {len(actual_frauds)}")
    print(f"ML Model Caught (Isolated): {len(ml_caught)}")
    print(f"Rule Engine Caught (Isolated): {len(rules_caught)}")
    print(f"Full System Caught (HIGH/CRITICAL): {true_positives}")
    
    print(f"\nSystem False Positives (Legit flagged HIGH/CRITICAL): {false_positives}")
    print(f"System False Negatives (Fraud flagged SAFE/LOW/MEDIUM): {false_negatives}")
    
    # Final Pipeline Recall & Precision
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / len(actual_frauds) if len(actual_frauds) > 0 else 0
    
    print(f"\nFinal Pipeline Precision: {precision:.4f}")
    print(f"Final Pipeline Recall: {recall:.4f}")
    print("----------------------------------")

if __name__ == "__main__":
    evaluate_pipeline()
