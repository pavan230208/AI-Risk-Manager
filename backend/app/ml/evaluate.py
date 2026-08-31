import os
import pandas as pd
from app.ml.features import extract_features
from app.ml.inference import risk_engine
from app.core.config import settings

_cached_metrics = None

def get_evaluation_metrics():
    global _cached_metrics
    if _cached_metrics is not None:
        return _cached_metrics

    # Load test dataset
    data_path = os.path.join(settings.DATA_DIR, "synthetic_transactions.csv")
    if not os.path.exists(data_path):
        return {"error": "Dataset not found"}

    df = pd.read_csv(data_path)
    test_df = df[df['split'] == 'test'].copy()

    # Extract features
    df_features = extract_features(test_df)

    if not risk_engine.is_ready:
        return {"error": "Model not ready"}

    X = df_features[risk_engine.features]
    X_scaled = risk_engine.scaler.transform(X)
    
    probabilities = risk_engine.model.predict_proba(X_scaled)[:, 1]
    predictions = probabilities >= risk_engine.threshold

    y_true = df_features.get('is_fraud', pd.Series([0]*len(test_df))).values
    
    tp = int(((y_true == 1) & (predictions == True)).sum())
    tn = int(((y_true == 0) & (predictions == False)).sum())
    fp = int(((y_true == 0) & (predictions == True)).sum())
    fn = int(((y_true == 1) & (predictions == False)).sum())

    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    _cached_metrics = {
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
    
    return _cached_metrics

