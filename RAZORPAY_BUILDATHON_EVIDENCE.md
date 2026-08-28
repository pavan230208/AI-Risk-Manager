# RAZORPAY BUILDATHON EVIDENCE PACKAGE

## Problem
The global digital economy suffers billions in losses due to sophisticated transaction fraud. Existing systems are often brittle, heavily reliant on manual human review, or entirely black-box AI systems that cannot guarantee execution safety in critical financial environments.

## Solution
The Autonomous AI Risk Manager is a provider-agnostic, multi-tenant fraud prevention platform. It seamlessly merges Machine Learning anomaly detection with a deterministic, fail-closed Policy Engine and ActionExecutor. This ensures that fraud is identified autonomously while execution boundaries remain mathematically safe and auditable.

## AI Integration
The AI (RandomForestClassifier) acts as the Risk Engine's sensory organ. Instead of explicitly executing a transaction, it evaluates features (velocity, location, amount) and emits a probability score. This score is mathematically synthesized with deterministic rules before crossing the execution boundary, preventing "AI Hallucinations" from directly blocking or approving money movement.

## Safety & Kill Switch
Because ML cannot directly execute financial actions, a catastrophic AI drift is neutralized by the deterministic Policy Engine. Furthermore, the system includes a global Kill Switch. When activated, all incoming automated transactions are intercepted and intercepted safely before execution, regardless of what the AI predicts.

## ML Metrics (Held-out Test Set)
- **Precision:** 0.1662
- **Recall:** 0.8158
- **F1 Score:** 0.2762
- **Accuracy:** 0.9133
- **Confusion Matrix:** TP: 62 | TN: 3363 | FP: 311 | FN: 14

## False Positive & Negative Cost Model
Operating at a 0.3 threshold optimizes business value:
- **False Positive Cost:** $10 per instance (friction)
- **False Negative Cost:** $500 per instance (loss)
- **Net Impact:** Simulating 10,000 transactions yields an estimated $73,300 in avoided losses after subtracting FP friction.

## Multi-Tenancy & Provider Independence
The system is built to support Razorpay, Stripe, UPI, or internal SaaS platforms simultaneously.
- **Provider Independence:** Webhooks hit adapter layers (`RazorpayAdapter`, `UPIAdapter`) that normalize varied third-party JSONs into our internal Risk Schema.
- **Multi-Tenancy:** Secure API keys cryptographically isolate Tenant A from Tenant B. Rate limits, event streams, and database queries are completely siloed.

## Reliability & Security
- **Fail-Closed:** Missing API keys, dropped Redis connections, or malfunctioning ML models result in safe rejection, never an open authorization.
- **Idempotency:** A Redis-backed concurrency layer ensures duplicate webhooks or double-clicks are ignored.
- **Security:** Hashed API keys, RBAC, strict payload validations, and 173 passing regression tests confirm platform integrity.

## Demonstration Flow (5-Minute Structure)
- **0:00-1:00:** Problem pitch and architectural explanation.
- **1:00-2:00:** Normal automated transaction flows into the Risk Engine and resolves as SAFE.
- **2:00-2:45:** High-velocity synthetic fraudulent transaction is automatically caught by ML/Rules and BLOCKED.
- **2:45-3:20:** The exact same fraud payload is resent (idempotency attack) and correctly ignored.
- **3:20-4:00:** Admin triggers the Kill Switch; system gracefully blocks incoming live integrations.
- **4:00-5:00:** Reveal the backend System Trace logging all events, then show ML Precision/Cost calculations.
