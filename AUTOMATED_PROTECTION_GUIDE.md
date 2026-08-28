# AUTOMATED PROTECTION GUIDE

The Autonomous AI Risk Manager can now be integrated directly into a company's software, analyzing every transaction instantly and autonomously via our secure API. 

## How It Works
1. **The Integration**: The company backend securely sends a transaction payload to the Risk Manager API before committing the business logic.
2. **Evaluation**: Our system instantly evaluates the context via ML inference, applies deterministic rule boundaries, and reaches an execution decision (ALLOW, REVIEW, or BLOCK).
3. **Execution Safety**: The ActionExecutor uses distributed Redis locks to ensure duplicates can never be evaluated and processed concurrently. 
4. **Resilience**: The system guarantees fail-closed behavior. If Redis goes offline, transactions are blocked. If the ML model is unavailable, the fallback heuristic safely processes or blocks according to strict rule policies.
5. **The Decision**: The company's backend acts on the Risk Manager's response to complete or reject the transaction.

## Enabling Automated Protection
Automated protection can be easily toggled on and off via the Risk Manager's Integration Dashboard.
- When **ON**, the `/api/v1/transactions/evaluate` endpoint securely accepts payloads, limits rate abuse, validates schema bounds, tracks metrics, and guards downstream behavior.
- When **OFF**, the API correctly rejects any incoming integrations with a safe HTTP 403 response, leaving the system in a safe manual-only state.

## Protection Mechanisms
- **Idempotency**: Identical `transaction_id` requests sent 100 times simultaneously will result in EXACTLY ONE execution. All others are harmlessly discarded as `IDEMPOTENT_DUPLICATE`.
- **Rate Limiting**: Protects your integration from DDOS and brute-force scaling abuse, strictly terminating traffic that exceeds thresholds with HTTP 429.
- **Fail-Closed Guarantee**: No transaction can succeed without full availability of the Redis EventBus, Postgres Datastore, and proper valid Authorization.
