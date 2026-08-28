import os
import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score, confusion_matrix
import json

from app.ml.features import extract_features

def compute_cost(y_true, y_pred, fp_cost=10, fn_cost=1000):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return fp * fp_cost + fn * fn_cost

def evaluate_model(model, X, y, threshold=0.5):
    probs = model.predict_proba(X)[:, 1]
    preds = (probs >= threshold).astype(int)
    
    return {
        "precision": float(precision_score(y, preds, zero_division=0)),
        "recall": float(recall_score(y, preds, zero_division=0)),
        "f1": float(f1_score(y, preds, zero_division=0)),
        "accuracy": float(accuracy_score(y, preds)),
        "confusion_matrix": confusion_matrix(y, preds).tolist(),
        "cost": float(compute_cost(y, preds))
    }

def train():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    csv_path = os.path.join(data_dir, "synthetic_transactions.csv")
    
    print("Loading dataset...")
    df = pd.read_csv(csv_path)
    
    print("Extracting features (applying identical pipeline)...")
    df = extract_features(df)
    
    # Define features
    feature_cols = ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']
    
    # Split isolation
    train_df = df[df['split'] == 'train']
    val_df = df[df['split'] == 'val']
    test_df = df[df['split'] == 'test']
    
    X_train = train_df[feature_cols]
    y_train = train_df['is_fraud']
    
    X_val = val_df[feature_cols]
    y_val = val_df['is_fraud']
    
    X_test = test_df[feature_cols]
    y_test = test_df['is_fraud']
    
    # Fit scaler strictly on Train
    print("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # 1. Baseline Model
    print("Training Logistic Regression Baseline...")
    baseline = LogisticRegression(class_weight='balanced', random_state=42)
    baseline.fit(X_train_scaled, y_train)
    
    # 2. XGBoost Model
    print("Training XGBoost Classifier...")
    # Calculate scale_pos_weight
    neg = len(y_train) - sum(y_train)
    pos = sum(y_train)
    scale_pos_weight = neg / pos if pos > 0 else 1
    
    xgb_model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    xgb_model.fit(X_train_scaled, y_train)
    
    # Threshold Optimization on Validation Set
    print("Optimizing threshold on Validation set (balancing precision, recall, and workload)...")
    thresholds = np.arange(0.1, 0.95, 0.05)
    best_threshold = 0.5
    best_f1 = 0.0
    
    xgb_probs = xgb_model.predict_proba(X_val_scaled)[:, 1]
    
    for t in thresholds:
        preds = (xgb_probs >= t).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        p = precision_score(y_val, preds, zero_division=0)
        r = recall_score(y_val, preds, zero_division=0)
        
        # Select highest F1 that maintains recall >= 0.98 to balance workload and detection
        if f1 > best_f1 and r >= 0.98:
            best_f1 = f1
            best_threshold = t
            
    print(f"Optimal Threshold selected: {best_threshold:.2f} with Validation F1 {best_f1:.4f}")
    
    # Final Evaluation on HELD-OUT TEST
    print("\n--- FINAL TEST EVALUATION ---")
    base_metrics = evaluate_model(baseline, X_test_scaled, y_test, threshold=0.5)
    xgb_metrics = evaluate_model(xgb_model, X_test_scaled, y_test, threshold=best_threshold)
    
    print("Baseline Metrics (Threshold 0.5):", json.dumps(base_metrics, indent=2))
    print(f"XGBoost Metrics (Threshold {best_threshold:.2f}):", json.dumps(xgb_metrics, indent=2))
    
    # Save Model Artifacts
    model_dir = os.path.join(data_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    
    artifacts = {
        "model": xgb_model,
        "scaler": scaler,
        "features": feature_cols,
        "optimal_threshold": float(best_threshold),
        "version": "1.0",
        "metrics": xgb_metrics
    }
    
    artifact_path = os.path.join(model_dir, "risk_model_v1.joblib")
    joblib.dump(artifacts, artifact_path)
    print(f"\nModel artifact saved to {artifact_path}")

if __name__ == "__main__":
    train()
