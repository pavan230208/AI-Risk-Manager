# PHASE 29: ML PERFORMANCE & COST-SENSITIVE RISK ANALYSIS

## 1. Dataset Description
The evaluation dataset is a synthetic transactions set crafted to mirror a financial transaction stream. It includes normal traffic alongside generated anomalous traffic involving high-risk locations, unusual velocities, and behavioral deviations.

- **Total Dataset Size (Held-out test set):** 3,750
- **Class Distribution:** 
  - `SAFE` (Negatives): 3,674
  - `FRAUD` (Positives): 76
- **Data-generation Methodology:** Configured synthetic generation mimicking typical financial indicators.
- **Train/Test Methodology:** Static chronological/random split. The training data was completely isolated from this 3,750-sample held-out set to prevent data leakage.
- **Model Used:** Random Forest Classifier (`risk_model_v1.joblib`).
- **Features Used:** Transaction amount, time-of-day proxies, device risk scores, IP reputation markers.

## 2. Cost Assumptions
To evaluate the true business impact of the Risk Engine, we apply a cost-sensitive evaluation model:
- **False Positive Cost ($10.00):** Operational overhead for manually reviewing a blocked legitimate transaction and associated customer dissatisfaction.
- **False Negative Cost ($500.00):** Expected financial liability, chargeback fees, and reputational damage from a missed fraudulent transaction.

## 3. Threshold Analysis & Confusion Matrices

### Threshold: 0.3
- **Precision:** 0.1662 | **Recall:** 0.8158 | **F1:** 0.2762
- **TP:** 62 | **TN:** 3363 | **FP:** 311 | **FN:** 14
- **FP Rate:** 8.46% | **FN Rate:** 18.42%
- **FP Cost:** $3,110.00 | **FN Cost:** $7,000.00
- **Total Cost:** $10,110.00

### Threshold: 0.5
- **Precision:** 0.2007 | **Recall:** 0.7895 | **F1:** 0.3200
- **TP:** 60 | **TN:** 3435 | **FP:** 239 | **FN:** 16
- **FP Rate:** 6.51% | **FN Rate:** 21.05%
- **FP Cost:** $2,390.00 | **FN Cost:** $8,000.00
- **Total Cost:** $10,390.00

### Threshold: 0.7
- **Precision:** 0.2522 | **Recall:** 0.7632 | **F1:** 0.3791
- **TP:** 58 | **TN:** 3502 | **FP:** 172 | **FN:** 18
- **FP Rate:** 4.68% | **FN Rate:** 23.68%
- **FP Cost:** $1,720.00 | **FN Cost:** $9,000.00
- **Total Cost:** $10,720.00

### Threshold: 0.85
- **Precision:** 0.4628 | **Recall:** 0.7368 | **F1:** 0.5685
- **TP:** 56 | **TN:** 3609 | **FP:** 65 | **FN:** 20
- **FP Rate:** 1.77% | **FN Rate:** 26.32%
- **FP Cost:** $650.00 | **FN Cost:** $10,000.00
- **Total Cost:** $10,650.00

## 4. Interpretation and Recommendations

- **Total Cost Optimization:** At the current cost assumptions ($10 FP / $500 FN), the lowest overall business cost ($10,110.00) is achieved at a relatively low threshold of `0.3`. While this yields a high number of False Positives (311), the severe penalty of False Negatives makes catching those extra 2 fraudulent transactions financially sensible. 
- **User Experience Optimization:** If the business determines that 311 False Positives per 3,750 transactions (an 8.46% interruption rate) causes unacceptable customer churn, the threshold can be raised to `0.85`. At this level, the interruption rate drops to just 1.77% (65 FP), but the business will absorb an extra $3,000 in fraud losses compared to the 0.3 threshold.
- **Production Implementation:** The ML Risk Engine merely outputs the probability. The Policy Engine (deterministic rules) maintains ultimate control. Thus, we can safely set the ML cutoff to a highly sensitive value (e.g., `0.3`) while using the Rule Engine to whitelist or auto-approve specific low-risk cohorts to mitigate the False Positive friction.

## 5. Limitations
- The dataset is synthetic; real-world adversaries adapt rapidly. Precision and recall metrics are snapshots in time.
- Cost estimates ($10 FP / $500 FN) are static and do not account for variable transaction amounts. A dynamic cost matrix (e.g., FN Cost = Transaction Amount) would yield a more precise threshold curve.
