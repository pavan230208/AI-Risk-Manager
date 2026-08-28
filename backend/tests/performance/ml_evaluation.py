import os
import sys
import pandas as pd
import json

# Add backend to path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine
from sklearn.metrics import confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score, accuracy_score

# Cost Assumptions
COST_FP = 10.0  # Cost of blocking a legitimate transaction (e.g. support cost, customer dissatisfaction)
COST_FN = 500.0 # Average cost of a missed fraudulent transaction (e.g. chargeback, financial loss)

def evaluate_ml_performance():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    csv_path = os.path.join(data_dir, "synthetic_transactions.csv")
    
    print("Loading HELD-OUT TEST dataset...")
    df = pd.read_csv(csv_path)
    test_df = df[df['split'] == 'test'].copy()
    
    print(f"Total test samples: {len(test_df)}")
    
    print("Extracting features...")
    df_features = extract_features(test_df)
    
    ml_engine = MLRiskEngine()
    
    results = []
    
    for idx, row in df_features.iterrows():
        single_tx_df = pd.DataFrame([row])
        ml_result = ml_engine.predict(single_tx_df)
        
        results.append({
            "is_fraud": row.get("is_fraud", 0),
            "probability": ml_result.get("probability", 0.0)
        })
        
    res_df = pd.DataFrame(results)
    y_true = res_df['is_fraud'].values
    y_prob = res_df['probability'].values
    
    thresholds = [0.3, 0.5, 0.7, 0.85]
    
    output = {
        "dataset_size": len(test_df),
        "class_distribution": {
            "SAFE": int(len(test_df[test_df['is_fraud'] == 0])),
            "FRAUD": int(len(test_df[test_df['is_fraud'] == 1]))
        },
        "cost_assumptions": {
            "false_positive_cost": COST_FP,
            "false_negative_cost": COST_FN
        },
        "thresholds": {}
    }
    
    try:
        roc_auc = roc_auc_score(y_true, y_prob)
    except:
        roc_auc = 0.0
    output["roc_auc"] = roc_auc
    
    print("\n=== COST-SENSITIVE RISK ANALYSIS ===")
    
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0,1]).ravel()
        
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        acc = accuracy_score(y_true, y_pred)
        
        fp_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
        fn_rate = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        fp_cost = fp * COST_FP
        fn_cost = fn * COST_FN
        total_cost = fp_cost + fn_cost
        
        output["thresholds"][str(t)] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "accuracy": float(acc),
            "confusion_matrix": {
                "TP": int(tp),
                "TN": int(tn),
                "FP": int(fp),
                "FN": int(fn)
            },
            "rates": {
                "false_positive_rate": float(fp_rate),
                "false_negative_rate": float(fn_rate)
            },
            "costs": {
                "fp_cost": float(fp_cost),
                "fn_cost": float(fn_cost),
                "total_cost": float(total_cost)
            }
        }
        
        print(f"\nThreshold: {t}")
        print(f"Precision: {precision:.4f} | Recall: {recall:.4f} | F1: {f1:.4f}")
        print(f"TP: {tp} | TN: {tn} | FP: {fp} | FN: {fn}")
        print(f"FP Rate: {fp_rate:.4f} | FN Rate: {fn_rate:.4f}")
        print(f"FP Cost: ${fp_cost:.2f} | FN Cost: ${fn_cost:.2f} | Total Cost: ${total_cost:.2f}")

    out_file = os.path.join(os.path.dirname(__file__), "ml_evaluation_results.json")
    # Make sure the directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(output, f, indent=4)
        
    print(f"\nResults saved to {out_file}")

if __name__ == "__main__":
    evaluate_ml_performance()
