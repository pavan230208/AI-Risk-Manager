# PHASE 28: ARCHITECTURE & IMPLEMENTATION PLAN

## 1. Current Architecture Relevant to Phase 28
The system currently implements a secure, fail-closed transaction evaluation pipeline:
- `POST /evaluate` (manual) and `POST /transactions/evaluate` (automated via API key).
- **Risk Engine:** ML fallback, Deterministic Rule Engine, Scorer, and Policy Engine.
- **Action Executor:** Redis-backed idempotency, authorization state tracking, fail-closed mechanism.
- **Authentication:** JWT for Admin endpoints, simple static `X-API-Key` checking against `settings.API_KEY` for integration endpoints.
- **Data Layer:** PostgreSQL (SQLAlchemy) with `transactions`, `transaction_features`, `risk_scores` tables.
- **Rate Limiter:** Redis-backed fixed window rate limiter (`rate_limiter.py`).

## 2. What Already Exists
- **Automated Monitoring Concept:** An integration endpoint `POST /transactions/evaluate` exists and is behind an `automation_state` toggle.
- **Rate Limiting:** A basic Redis-backed rate limiter is already active on the integration endpoint.
- **Idempotency & Fail-closed:** The Action Executor and Redis-backed state tracking correctly implement idempotency based on `transaction_id`.
- **Database Models:** Basic transaction tracking exists but lacks tenant isolation.

## 3. What is Missing
1. **API Key Lifecycle & Tenant Isolation:** No database models exist for `Tenant` or `APIKey`. The integration auth uses a single hardcoded API Key.
2. **Multi-tenant Tracking:** `transactions`, `risk_scores`, and audit events lack a `tenant_id` field.
3. **Provider-Agnostic Normalization:** `TransactionPayload` expects specific fields. It lacks a normalization layer to accept varied provider formats and convert them to a standard internal schema.
4. **Enhanced Mobile-Ready API:** Need consistent JSON structures consumable by Web/Android/iOS.
5. **UI Updates for Automated Monitoring:** The frontend needs to clearly segregate "Manual Mode" and "Automated Monitoring", displaying actual stats per tenant.

## 4. Implementation Plan
### Step 1: Database Schema Expansion
- Create `Tenant` and `APIKey` models in a new `app/models/tenant.py`.
- Add `tenant_id` to `Transaction` model (`app/models/transaction.py`).
- Generate and apply Alembic migrations (if applicable) or rely on `Base.metadata.create_all` for the testing environment.

### Step 2: Security & Authentication Updates
- Modify `app/api/auth.py` -> `verify_integration_api_key` to query the database (or cache) for active API keys instead of the hardcoded setting. 
- Return the `tenant_id` from the auth dependency.
- Create API endpoints for API Key Lifecycle (Create, Rotate, Revoke) restricted to Admin.

### Step 3: Provider-Agnostic Normalization
- Create `app/services/normalizer.py` to handle incoming payloads.
- Update `TransactionPayload` to include generic `metadata: Dict[str, Any]` and allow provider-specific schemas to map to the internal structure.

### Step 4: Router & Core Workflow Updates
- Update `POST /transactions/evaluate` to accept the `tenant_id` from auth.
- Pass `tenant_id` through the evaluation pipeline (db tracking, audit events, rate limiter).
- Ensure the rate limiter uses `tenant_id` as the client key.

### Step 5: Frontend UX Overhaul
- Modify `page.tsx` to explicitly separate "Manual Analysis" and "Automated Monitoring".
- Fetch tenant stats for the automated monitoring view (if admin/tenant).

### Step 6: Testing & Validation
- Add pytest cases for: Tenant Isolation, API Key Revocation, Provider Normalization.
- Run `pytest` to ensure 149+ tests pass.
- Run frontend build.
