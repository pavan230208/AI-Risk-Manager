import os
import pandas as pd
from app.ml.features import extract_features
from app.ml.inference import risk_engine
from app.core.config import settings

_live_metrics_state = None

def _initialize_baseline():
    global _live_metrics_state
    if _live_metrics_state is not None:
        return

    data_path = os.path.join(settings.DATA_DIR, "synthetic_transactions.csv")
    if not os.path.exists(data_path):
        return

    df = pd.read_csv(data_path)
    test_df = df[df['split'] == 'test'].copy()
    df_features = extract_features(test_df)
    
    if not risk_engine.is_ready:
        return

    X = df_features[risk_engine.features]
    X_scaled = risk_engine.scaler.transform(X)
    
    probabilities = risk_engine.model.predict_proba(X_scaled)[:, 1]
    predictions = probabilities >= risk_engine.threshold
    y_true = df_features.get('is_fraud', pd.Series([0]*len(test_df))).values
    
    tp = int(((y_true == 1) & (predictions == True)).sum())
    tn = int(((y_true == 0) & (predictions == False)).sum())
    fp = int(((y_true == 0) & (predictions == True)).sum())
    fn = int(((y_true == 1) & (predictions == False)).sum())

    _live_metrics_state = {
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "total_test_samples": tp + tn + fp + fn
    }

def record_live_evaluation(is_fraud: bool, predicted_fraud: bool):
    global _live_metrics_state
    if _live_metrics_state is None:
        _initialize_baseline()
        if _live_metrics_state is None:
            return
            
    _live_metrics_state["total_test_samples"] += 1
    if is_fraud and predicted_fraud:
        _live_metrics_state["true_positives"] += 1
    elif not is_fraud and predicted_fraud:
        _live_metrics_state["false_positives"] += 1
    elif not is_fraud and not predicted_fraud:
        _live_metrics_state["true_negatives"] += 1
    else:
        _live_metrics_state["false_negatives"] += 1

def get_evaluation_metrics():
    global _live_metrics_state
    if _live_metrics_state is None:
        _initialize_baseline()
        
    if _live_metrics_state is None:
        return {"error": "Could not initialize metrics"}
        
    tp = _live_metrics_state["true_positives"]
    tn = _live_metrics_state["true_negatives"]
    fp = _live_metrics_state["false_positives"]
    fn = _live_metrics_state["false_negatives"]
    total = _live_metrics_state["total_test_samples"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "test_samples": total,
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1),
        "confusion_matrix": {
            "true_positive": tp,
            "false_negative": fn,
            "false_positive": fp,
            "true_negative": tn
        }
    }
