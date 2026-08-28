# FINAL EXPLAINABILITY SPEC

## Objective
To ensure every automated and manual risk decision is auditable, transparent, and debuggable without leaking sensitive credentials or PII.

## Standard JSON Response
Every transaction evaluated returns a structured risk response. 
```json
{
    "transaction_id": "TXN-12345",
    "correlation_id": "corr-uuid",
    "tenant_id": "TENANT_A",
    "ml_probability": 0.89,
    "ml_status": "SUCCESS",
    "rule_signals": ["HIGH_AMOUNT", "VELOCITY_SPIKE"],
    "final_score": 0.95,
    "risk_level": "CRITICAL",
    "policy_action": "BLOCK",
    "human_approval_required": true,
    "authorization_state": "DENIED",
    "execution_status": "BLOCKED_BY_POLICY",
    "policy_version": "1.0",
    "model_version": "1.0",
    "explanation": "Score 0.95 exceeded threshold 0.85.",
    "timestamp": "2026-08-28T14:00:00Z"
}
```

## Traceability Guarantees
- **No Secrets Exposed:** JWTs, API Keys, and raw provider payloads are systematically stripped before JSON serialization.
- **Audit References:** The `correlation_id` allows operators to query the Redis EventBus to view the exact deterministic timeline.
- **Explainable Action:** The `explanation` field explicitly maps the `final_score` to the executed `policy_action`.
