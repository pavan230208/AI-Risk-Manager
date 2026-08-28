import os
import sys
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
import json

# Setup paths
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine
from app.risk.rule_engine import DeterministicRuleEngine
from app.risk.scorer import RiskScorer
from app.core.config import settings

def run_diagnostics():
    print("============================================================")
    print("STARTING DIAGNOSTIC EVALUATION")
    print("============================================================")
    
    # 1. Load Data
    data_dir = os.path.join(backend_dir, "data")
    csv_path = os.path.join(data_dir, "synthetic_transactions.csv")
    df = pd.read_csv(csv_path)
    
    # 2. Extract Features
    df = extract_features(df)
    
    # 3. Splits
    val_df = df[df['split'] == 'val'].copy()
    test_df = df[df['split'] == 'test'].copy()
    
    feature_cols = ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']
    
    X_val = val_df[feature_cols]
    y_val = val_df['is_fraud']
    
    X_test = test_df[feature_cols]
    y_test = test_df['is_fraud']
    
    # Load ML Model
    model_path = os.path.join(data_dir, "models", "risk_model_v1.joblib")
    artifacts = joblib.load(model_path)
    model = artifacts["model"]
    scaler = artifacts["scaler"]
    optimal_threshold = artifacts["optimal_threshold"]
    
    X_test_scaled = scaler.transform(X_test)
    X_val_scaled = scaler.transform(X_val)
    
    print("\n============================================================")
    print("1. PRECISION/RECALL ANALYSIS (HELD-OUT TEST)")
    print("============================================================")
    
    probs_test = model.predict_proba(X_test_scaled)[:, 1]
    preds_test = (probs_test >= optimal_threshold).astype(int)
    
    tn, fp, fn, tp = confusion_matrix(y_test, preds_test).ravel()
    precision = precision_score(y_test, preds_test, zero_division=0)
    recall = recall_score(y_test, preds_test, zero_division=0)
    f1 = f1_score(y_test, preds_test, zero_division=0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
    
    print(f"Total Transactions: {len(y_test)}")
    print(f"Actual Fraud: {sum(y_test)}")
    print(f"ML Detections: {sum(preds_test)}")
    print("\nConfusion Matrix:")
    print(f"                Predicted Legit    Predicted Risk")
    print(f"Actual Legit    {tn:<18} {fp}")
    print(f"Actual Fraud    {fn:<18} {tp}")
    print("\nMetrics:")
    print(f"TP: {tp}, TN: {tn}, FP: {fp}, FN: {fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1: {f1:.4f}")
    print(f"False Positive Rate: {fpr:.4f}")
    print(f"False Negative Rate: {fnr:.4f}")
    
    print("\n============================================================")
    print("2. THRESHOLD ANALYSIS (VALIDATION SET)")
    print("============================================================")
    
    probs_val = model.predict_proba(X_val_scaled)[:, 1]
    
    print(f"{'Threshold':<10} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} | {'Review Vol':<12}")
    print("-" * 65)
    for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        preds = (probs_val >= t).astype(int)
        p = precision_score(y_val, preds, zero_division=0)
        r = recall_score(y_val, preds, zero_division=0)
        f = f1_score(y_val, preds, zero_division=0)
        vol = sum(preds)
        print(f"{t:<10.2f} | {p:<10.4f} | {r:<10.4f} | {f:<10.4f} | {vol:<12}")
    
    print("\n============================================================")
    print("3. RULE ENGINE INVESTIGATION (HELD-OUT TEST)")
    print("============================================================")
    
    rule_engine = DeterministicRuleEngine()
    
    rule_stats = {}
    ml_detected = set()
    rule_detected = set()
    
    for i in range(len(test_df)):
        tx_row = test_df.iloc[i]
        is_fraud = bool(tx_row['is_fraud'])
        pred_ml = bool(preds_test[i])
        
        tx_dict = tx_row.to_dict()
        features_dict = {
            'velocity_1h': tx_dict.get('velocity_1h', 0),
            'velocity_24h': tx_dict.get('velocity_24h', 0),
            'is_new_device': tx_dict.get('is_new_device', 0),
            'is_new_location': tx_dict.get('is_new_location', 0),
            'amount_deviation': tx_dict.get('amount_deviation', 1.0)
        }
        
        signals = rule_engine.evaluate(tx_dict, features_dict)
        
        if pred_ml:
            ml_detected.add(i)
        
        if signals:
            rule_detected.add(i)
            for s in signals:
                r_name = s.rule_name
                if r_name not in rule_stats:
                    rule_stats[r_name] = {'total': 0, 'legit': 0, 'fraud': 0}
                rule_stats[r_name]['total'] += 1
                if is_fraud:
                    rule_stats[r_name]['fraud'] += 1
                else:
                    rule_stats[r_name]['legit'] += 1
                    
    print("Rule Triggers:")
    for r_name, stats in rule_stats.items():
        prec = stats['fraud'] / stats['total'] if stats['total'] > 0 else 0
        print(f"Rule: {r_name}")
        print(f"  Total: {stats['total']}, Legit: {stats['legit']}, Fraud: {stats['fraud']}")
        print(f"  Precision: {prec:.4f}")
        
    actual_frauds = set(np.where(y_test == 1)[0])
    
    ml_fraud = ml_detected.intersection(actual_frauds)
    rule_fraud = rule_detected.intersection(actual_frauds)
    
    only_ml = len(ml_fraud - rule_fraud)
    only_rule = len(rule_fraud - ml_fraud)
    both = len(ml_fraud.intersection(rule_fraud))
    
    print("\nOverlap Analysis:")
    print(f"Fraud detected ONLY by ML: {only_ml}")
    print(f"Fraud detected ONLY by rules: {only_rule}")
    print(f"Fraud detected by BOTH: {both}")
    
    print("\n============================================================")
    print("7. HUMAN REVIEW WORKLOAD")
    print("============================================================")
    
    # Combined system workload (using RiskScorer)
    scorer = RiskScorer()
    high_critical_count = 0
    actual_fraud_in_queue = 0
    legit_in_queue = 0
    
    for i in range(len(test_df)):
        tx_row = test_df.iloc[i]
        is_fraud = bool(tx_row['is_fraud'])
        prob = float(probs_test[i])
        
        tx_dict = tx_row.to_dict()
        features_dict = {
            'velocity_1h': tx_dict.get('velocity_1h', 0),
            'velocity_24h': tx_dict.get('velocity_24h', 0),
            'is_new_device': tx_dict.get('is_new_device', 0),
            'is_new_location': tx_dict.get('is_new_location', 0),
            'amount_deviation': tx_dict.get('amount_deviation', 1.0)
        }
        
        signals = rule_engine.evaluate(tx_dict, features_dict)
        
        ml_result = {"status": "success", "probability": prob, "is_risky": prob >= optimal_threshold}
        
        score_result = scorer.calculate_score(
            ml_result=ml_result,
            rule_signals=signals
        )
        
        if score_result.risk_level in ["HIGH", "CRITICAL"]:
            high_critical_count += 1
            if is_fraud:
                actual_fraud_in_queue += 1
            else:
                legit_in_queue += 1
                
    total_tx = len(test_df)
    pct_review = (high_critical_count / total_tx) * 100 if total_tx > 0 else 0
    
    print(f"Total Transactions: {total_tx}")
    print(f"Total HIGH/CRITICAL (Review Queue): {high_critical_count}")
    print(f"Percentage sent to Human Review: {pct_review:.2f}%")
    print(f"Actual Fraud in Review Queue: {actual_fraud_in_queue}")
    print(f"Legitimate Transactions in Review Queue: {legit_in_queue}")

if __name__ == "__main__":
    run_diagnostics()
