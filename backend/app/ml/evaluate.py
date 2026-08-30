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
    
    df = pd.read_csv(csv_path)
    test_df = df[df['split'] == 'test'].copy()
    
    df_features = extract_features(test_df)
    
    ml_engine = MLRiskEngine()
    rule_engine = DeterministicRuleEngine()
    scorer = RiskScorer()
    
    results = []
    
    for idx, row in df_features.iterrows():
        single_tx_df = pd.DataFrame([row])
        ml_result = ml_engine.predict(single_tx_df)
        
        tx_dict = row.to_dict()
        signals = rule_engine.evaluate(tx_dict, tx_dict)
        
        score_result = scorer.calculate_score(ml_result, signals)
        
        results.append({
            "is_fraud": tx_dict.get("is_fraud", 0),
            "final_score": score_result.final_score,
            "risk_level": score_result.risk_level,
            "ml_risky": ml_result.get("is_risky", False),
            "rule_caught": len(signals) > 0
        })
        
    res_df = pd.DataFrame(results)
    
    actual_frauds = res_df[res_df['is_fraud'] == 1]
    actual_legits = res_df[res_df['is_fraud'] == 0]
    
    system_flagged = res_df[res_df['risk_level'].isin(['HIGH', 'CRITICAL'])]
    
    true_positives = len(system_flagged[system_flagged['is_fraud'] == 1])
    false_positives = len(system_flagged[system_flagged['is_fraud'] == 0])
    false_negatives = len(actual_frauds) - true_positives
    true_negatives = len(actual_legits) - false_positives
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / len(actual_frauds) if len(actual_frauds) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (true_positives + true_negatives) / len(res_df) if len(res_df) > 0 else 0
    
    fpr = false_positives / len(actual_legits) if len(actual_legits) > 0 else 0
    fnr = false_negatives / len(actual_frauds) if len(actual_frauds) > 0 else 0
    
    return {
        "test_samples": len(test_df),
        "total_frauds": len(actual_frauds),
        "total_legits": len(actual_legits),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "true_negatives": true_negatives,
        "false_negatives": false_negatives,
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "accuracy": float(accuracy),
        "fpr": float(fpr),
        "fnr": float(fnr)
    }

_cached_metrics = None
def get_evaluation_metrics():
    global _cached_metrics
    if _cached_metrics is None:
        _cached_metrics = evaluate_pipeline()
    return _cached_metrics

if __name__ == "__main__":
    import pprint
    pprint.pprint(evaluate_pipeline())
