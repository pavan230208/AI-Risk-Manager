# FINAL ML EVIDENCE REPORT

## Overview
This report documents the measurable performance of the ML Risk Engine integrated into the Autonomous AI Risk Manager. The evaluation is designed to simulate real-world financial transaction risk analysis using a cost-sensitive evaluation model.

## Dataset Details
- **Source/Origin:** Internally generated synthetic dataset configured to mimic standard financial fraud patterns (high-risk locations, impossible velocities, IP anomalies).
- **Size:** 3,750 held-out test records.
- **Class Distribution:** 
  - SAFE (Negatives): 3,674
  - FRAUD (Positives): 76
- **Features Used:** `amount`, `hour_of_day`, `is_high_risk_location`, `device_risk_score`, `velocity_24h`
- **Target:** `is_fraud` (0 or 1)

## Methodology
- **Train/Test Split:** A strict chronological split. The training data was completely isolated from this test set.
- **Leakage Prevention:** Features are extracted independently per transaction. No forward-looking information is used.
- **Model:** Scikit-Learn `RandomForestClassifier`.
- **Deterministic Fallback:** If the ML model is unavailable or throws an exception, the system fails closed gracefully and falls back to deterministic Rule Engine checks.

## Measured Performance (Held-out Test Set)
At the optimal business threshold (0.3):
- **Precision:** 0.1662
- **Recall:** 0.8158
- **F1 Score:** 0.2762
- **Accuracy:** 0.9133
- **Confusion Matrix:** TP: 62 | TN: 3363 | FP: 311 | FN: 14

## Limitations & Assumptions
- **Synthetic Limitations:** The dataset is synthetic. Real-world adversaries adapt, and real-world precision will likely be lower until trained on live domain data.
- **Expected Production Behavior:** The ML model operates as an advisory input. It does NOT execute transactions. High probability scores trigger human review or immediate block policies in the deterministic Policy Engine.

## Reproducibility
Run `python tests/performance/ml_evaluation.py` to deterministically regenerate the metrics and cost analysis.
