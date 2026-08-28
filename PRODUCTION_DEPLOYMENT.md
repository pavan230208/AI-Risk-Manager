# Production Deployment Guide

## Architecture Overview
The Autonomous AI Risk Manager uses a microservices-style architecture composed of:
1. **FastAPI Backend**: Handles risk evaluation and rule processing.
2. **PostgreSQL**: Primary transactional database.
3. **Redis**: In-memory store for idempotency locking and Event Bus messaging.
4. **Next.js Frontend**: Operational dashboard.

## Deployment Requirements
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+
- Python 3.10+

## Environment Configuration
The application strictly fails closed. You **MUST** provide a `.env` file with the following variables:
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@host:5432/risk_manager
REDIS_URL=redis://host:6379/0
EVENT_BUS_BACKEND=redis
JWT_SECRET=CHANGE_ME_TO_A_LONG_RANDOM_SECRET_AT_LEAST_32_BYTES
API_KEY=CHANGE_ME_TO_A_SECURE_API_KEY
BACKEND_CORS_ORIGINS=["https://your-production-domain.com"]
MAX_REQUEST_SIZE_BYTES=1048576
```
**Security Note:** `JWT_SECRET` has no default and must be >= 32 characters in production. `EVENT_BUS_BACKEND` must be `redis`. If missing, the backend will fatally crash on startup to prevent insecure fail-open behavior.

## Database Migrations
We use Alembic for PostgreSQL schema migrations.
```bash
# Run migrations to initialize the schema
PYTHONPATH="backend" alembic -c backend/alembic.ini upgrade head
```

## Security & Network Hardening
1. **CORS**: Production explicitly restricts origins. Configure `BACKEND_CORS_ORIGINS` in your environment.
2. **API Keys**: The `/api/v1/evaluate` endpoint requires the `X-API-Key` header when `ENVIRONMENT=production`.
3. **Internal Endpoints**: `/health/liveness` and `/health/readiness` are exposed for Kubernetes/Docker orchestration.

## Backup and Recovery
### Implemented Strategy
- **PostgreSQL**: We recommend daily `pg_dump` automated cron jobs.
- **Redis**: The system tolerates Redis failures (locks simply expire or fail safe). Redis persistence (RDB/AOF) can be configured if exact DLQ retention is desired across restarts, but the primary source of truth remains PostgreSQL.

### Disaster Recovery
If the database corrupts:
1. Restore the latest `pg_dump`.
2. All pending transactions during the downtime will have been gracefully rejected (Failed-Closed).

## Container Security
The `docker-compose.yml` runs alpine images minimizing attack surfaces. We recommend running the FastAPI container as a non-root user in enterprise deployments.

## Metrics & Observability
All risk decisions (SAFE, SUSPICIOUS, CRITICAL) emit structured JSON events to the Redis Event Bus with a unique `correlation_id` and `action_id`. PII and secrets are strictly excluded from logging.

## Fail-Safe Invariants
- **NEVER FAIL OPEN**: If PostgreSQL dies, transactions are rejected.
- **NEVER FAIL OPEN**: If Redis dies, idempotency cannot be guaranteed, transactions are rejected.
- **NEVER FAIL OPEN**: If the ML engine crashes or returns NaN, the system degrades to deterministic rules.
