# PHASE 28 STEP 1: API KEY & TENANT REPORT

## Baseline vs Final
- **Baseline:** 154 passed / 3 failed (PostgreSQL connection issues) / 0 skipped.
- **Final:** 164 passed / 0 failed / 0 skipped. (10 additional passes: 7 new tests + 3 Postgres tests resolving via Docker).

## Database Schema
Added the `Tenant` and `APIKey` tables to `backend/app/models/tenant.py`.
- **Tenant:** Tracks tenant ID, name, active status, creation/update timestamps.
- **APIKey:** Tracks key ID, associated `tenant_id`, `key_prefix` (for lookup without full key), `key_hash` (for secure validation), name, active status, revocation status, revocation timestamps, expiration, and last used times.
- **Transaction:** Added a nullable `tenant_id` Foreign Key to the `Transaction` model in `app/models/transaction.py` for backward compatibility while introducing multi-tenancy. 

## Security Design
- **API Key Lifecycle:** API Keys are generated with a prefix (e.g. `pk_live_xxxx...`) and a securely generated random secret. The raw secret is **never stored**. Only the `key_prefix` and the `key_hash` (currently simulated with SHA256, ready for Argon2/Bcrypt) are saved to the database.
- **Tenant Isolation:** By tracking the `tenant_id` on the `APIKey` table, all incoming requests authenticated via an API Key will be definitively bound to the single tenant that owns the key. The client cannot manually forge a `tenant_id`.

## Migrations Performed
- Ran `alembic revision --autogenerate -m "Add Tenant and APIKey models"`
- Ran `alembic upgrade head`
- Validated migration successfully applied against the REAL PostgreSQL Docker container.

## Tests Performed
Created `tests/test_28_api_keys.py` to cover:
- Tenant creation & API key generation.
- Valid API key authentication (hash matching).
- Rejection of invalid API key.
- Rejection of revoked API key (`is_revoked = True`).
- Rejection of expired API key.
- Rejection if the associated Tenant is inactive (`is_active = False`).
- Tenant isolation (preventing Tenant A's API key from identifying as Tenant B).
- Verification that raw secrets are **NOT** stored or exposed.

## Failures Discovered & Fixes Implemented
- **Issue:** PostgreSQL tests initially failed due to the local container not running.
- **Fix:** Booted the PostgreSQL Docker container via `docker-compose up -d`. All PostgreSQL integration tests now pass.
- **Issue:** Minor import issue in the new test file (`app.db.session` vs `app.db.database`).
- **Fix:** Corrected import path, tests executed successfully.

## Remaining Risks
- The current integration API endpoint `POST /transactions/evaluate` still uses the legacy hardcoded `API_KEY` for backward compatibility. In Step 2, this needs to be swapped out for a database-backed API Key validation function.
- SHA-256 is used as a placeholder hash in testing; a stronger algorithm (e.g., Argon2id or Bcrypt) must be enforced for actual production key hashing.
- The `tenant_id` on the `Transaction` table is `nullable=True` to preserve legacy logic; this should eventually be tightened if the system strictly enforces multi-tenancy.
