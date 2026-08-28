# DEPLOYMENT RUNBOOK

This runbook acts as the final guide for moving the AI Risk Manager into an active cloud architecture.

## 1. Cloud Architecture

### Frontend
- **Provider:** Vercel or DigitalOcean App Platform.
- **Config:** Expose `NEXT_PUBLIC_API_URL` pointing strictly to the HTTPS backend endpoint.

### Backend
- **Provider:** DigitalOcean App Platform / AWS ECS.
- **Container:** Dockerized via existing `Dockerfile` and Gunicorn worker bindings.

### Persistence Layers
- **Database:** Managed PostgreSQL (e.g., DigitalOcean Managed Databases).
- **Cache / Locks:** Managed Redis.

## 2. Environment Variables & Secret Configuration
These MUST be injected via your hosting provider's secure Vault/Config pane.
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://usr:pwd@host:port/db
REDIS_URL=redis://usr:pwd@host:port
JWT_SECRET=secure-64-byte-hex-string
```

## 3. Database Migration Strategy
**Critical:** Migrations must execute *before* the backend application spins up and serves traffic.
- Configure a Pre-Deploy command on the Backend container:
  ```bash
  alembic upgrade head
  ```
- If the exit code is non-zero, the platform must abort the deployment natively.

## 4. HTTPS & CORS
- The cloud provider's ingress layer MUST handle SSL termination.
- Backend CORS allowed origins must be updated in `app/core/config.py` to match the exact Vercel/DO Frontend deployment URL (e.g. `https://my-risk-app.vercel.app`).

## 5. Health Checks & Monitoring
- **Liveness:** `GET /health/liveness` — Verifies FastAPI is not deadlocked.
- **Readiness:** `GET /health/readiness` — Verifies connections to Postgres and Redis are active. If not, the Load Balancer stops sending traffic.

## 6. Rollback & Disaster Recovery
- **Database Backups:** Rely on Managed Database automated daily snapshots and point-in-time recovery.
- **App Rollback:** Zero-downtime deployment capabilities of ECS / App Platform allow immediate reversion to prior image hashes. Redis cache states (Idempotency tokens) can be flushed safely if required since they only protect immediate temporal concurrency.
