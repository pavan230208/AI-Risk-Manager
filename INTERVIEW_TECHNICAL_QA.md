# INTERVIEW TECHNICAL Q&A

**1. What makes this different from a normal fraud classifier?**
We don't merely predict fraud. We safely manage what happens *after* the prediction. A normal classifier just gives a score; our system provides a mathematically sound execution boundary (ActionExecutor) that enforces idempotency, policies, and a Kill Switch.

**2. Why use ML if deterministic rules exist?**
Deterministic rules catch known fraud patterns (e.g., "Amount > 10,000 AND Location = 'Suspicious'"). ML identifies subtle, multivariate correlations that evade static rules. 

**3. Why can't the LLM/AI directly make the transaction decision?**
AI is non-deterministic and can hallucinate or drift. Giving AI direct execution authority over financial ledgers is reckless. By placing a deterministic Policy Engine between the AI and the ActionExecutor, we guarantee safety invariants are never broken.

**4. How do you prevent duplicate execution?**
We use Redis to generate and track execution tokens via the transaction ID. If multiple identical requests hit the server concurrently, the Redis atomic locks ensure only the first one executes, while the others receive an `IDEMPOTENT_DUPLICATE` response.

**5. Why Redis?**
Redis provides single-threaded atomic operations which are mathematically perfect for distributed idempotency and distributed rate limiting, far faster than Postgres transactions for high-throughput locking.

**6. Why PostgreSQL?**
PostgreSQL is ACID compliant and guarantees the long-term relational integrity of transaction records, API keys, and audit logs.

**7. How does tenant isolation work?**
Incoming API keys are hashed and matched to an `APIKey` record, which contains a strict `tenant_id`. This ID is injected into the request context and forcefully applied to all database queries and Redis namespace keys.

**8. What happens if Redis goes down?**
The ActionExecutor will fail to acquire the required idempotency lock. Because the architecture is "fail-closed", the transaction is rejected rather than risking a duplicate charge. 

**9. What happens if the ML model crashes?**
The `MLRiskEngine` traps the exception and returns a fallback status. The system continues to operate using the deterministic Rule Engine, ensuring a graceful degradation of service rather than total outage.

**10. How did you measure precision and recall?**
We evaluated the model against an isolated, held-out test set of 3,750 synthetic transactions to simulate real-world conditions without data leakage.

**11. What is your false-positive cost?**
We estimate $10 per false positive (operational review friction). At a 0.3 threshold on 10,000 transactions, we incur $8,200 in FP friction but prevent $81,500 in actual fraud loss.

**12. How would Razorpay integrate it?**
Razorpay would configure a webhook to point to our `/api/v1/webhooks/transactions?provider=razorpay` endpoint. We supply them an API key.

**13. What is the biggest limitation?**
Currently, our datasets are synthetic. Real-world fraud detection accuracy relies heavily on vast amounts of real-world historical data which we lack access to as an independent project.
