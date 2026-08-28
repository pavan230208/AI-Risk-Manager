# PROJECT ARCHITECTURE GUIDE: AI RISK MANAGER

## 1. Problem Statement
Modern financial systems process millions of autonomous transactions per second. When ML models are directly connected to transaction execution, unpredictable model hallucinations or feature drift can lead to massive unauthorized fund transfers, creating severe financial and regulatory risks.

## 2. Why Existing Systems Fail
Traditional systems either:
1. Rely purely on rigid static rules (too slow for new fraud patterns).
2. Allow ML models to execute actions directly (violating deterministic safety and failing open during outages).

## 3. Project Objective
Build a production-grade, fail-safe AI Risk Manager that evaluates transactions in real-time using ML, but **never** allows the ML model to authorize execution directly. All execution is governed by a deterministic Rule Engine and Policy Layer.

## 4. System Architecture
The system uses a pipeline architecture: API Gateway -> Feature Engineering -> ML Risk Scoring -> Deterministic Rule Engine -> Policy Engine -> Action Executor -> Redis Idempotency -> PostgreSQL. 

## 5. Transaction Flow
1. Transaction received via API.
2. Features extracted (time, velocity, IP, etc.).
3. ML model predicts fraud probability.
4. Deterministic Rule Engine evaluates hard signals.
5. Risk Scorer merges ML and Rule signals.
6. Policy Engine determines ALLOW, BLOCK, or PENDING_APPROVAL.
7. Action Executor handles execution based on Policy.

## 6. ML Role
The ML model acts strictly as an **advisory signal**. It outputs a probability score but has no execution authority. If the ML model fails, the system safely falls back to deterministic rules.

## 7. Rule Engine Role
The Rule Engine acts as the definitive safety net. It can override the ML model (e.g., if a transaction exceeds $10,000, it requires human approval, regardless of ML confidence).

## 8. Risk Scoring
The Risk Scorer generates a deterministic integer from 0-100 based on ML output and rule signals, creating an explainable risk metric.

## 9. Policy Engine
Translates the Risk Score into a concrete action: `ALLOW`, `PENDING_APPROVAL`, `BLOCK`, `DENIED`.

## 10. Action Executor
The component responsible for side-effects (e.g., database writes). It refuses to execute if the system is in Kill Switch mode or if the transaction is a duplicate.

## 11. Redis Idempotency
Prevents replay attacks or network retry bugs by ensuring every `correlation_id` is executed exactly once using atomic Redis locks.

## 12. PostgreSQL
The source of truth for transaction state, human approvals, and configuration.

## 13. EventBus
Publishes all state changes to a Redis Stream for real-time auditability and decoupled downstream processing.

## 14. RBAC
Role-Based Access Control ensures only ADMIN users can activate the Kill Switch or approve PENDING transactions.

## 15. Kill Switch
An emergency administrative control that disables all autonomous execution, forcing all new transactions into a safe `PENDING_APPROVAL` state.

## 16. Fail-closed Architecture
If Redis fails, Postgres fails, or ML fails, the system rejects the transaction. It NEVER fails open.

## 17. Reconciliation
If a transaction outcome is uncertain (e.g., network partition during execution), it is marked `RECONCILIATION_REQUIRED` for manual review, preventing blind retries.

## 18. Security Model
- JWT Authentication
- API Key Protection
- Strict Payload Size limits
- Fail-closed Idempotency
- Feature Fuzzing resilience

## 19. Deployment Architecture
Docker Compose managing Next.js frontend, FastAPI backend, PostgreSQL, and Redis.

## 20. Testing Strategy
- Unit tests for core logic
- Integration tests for APIs
- Adversarial tests (Fuzzing, ML failures)
- Infrastructure failure drills
- End-to-end frontend/backend tests (149+ passing)

## 21. Performance Results
Handles high concurrency gracefully with bounded latency, validating the asynchronous EventBus design.

## 22. Failure Drill Results
System correctly downgrades to safe states when Redis/Postgres/ML dependencies are terminated unexpectedly.

## 23. Known Limitations
- Next.js currently handles authentication tokens locally for the demo instead of using Next-Auth.
- Need a distributed tracing system (e.g., Jaeger) for deeper multi-service observability.

## 24. Future Improvements
- Kubernetes Helm charts for distributed deployment.
- OAuth2/OIDC integration.
- Automated retraining pipelines for the ML model.

---

### Explain this project in 60 seconds
"This project is a fail-safe AI Risk Manager for financial transactions. It solves the danger of autonomous AI by ensuring an ML model never directly executes a transaction. Instead, the ML acts as an advisory signal, while a deterministic Rule and Policy Engine maintain ultimate authority. It features built-in idempotency, a fail-closed architecture, and an emergency Kill Switch, making it production-ready for high-stakes environments."

### Explain this project technically in 3 minutes
"We built an event-driven architecture using Next.js, FastAPI, Redis, and PostgreSQL. When a transaction arrives, it passes through a temporally isolated feature extraction pipeline, then to an ML scorer. The ML outputs a probability, which is then fed into a deterministic Rule Engine that evaluates hard constraints. A Policy Engine then maps this combined risk score to an authorization state. Before any side-effects occur, an Action Executor checks a Redis-backed idempotency lock to prevent duplicates. If authorized, the transaction state is persisted to Postgres, and an event is published to a Redis EventBus for the frontend audit trail. The entire system is designed to fail-closed—if Redis, Postgres, or the ML model goes down, transactions are safely rejected. We've also implemented strict JWT RBAC for administrative actions like the Kill Switch, which globally disables autonomous execution."
