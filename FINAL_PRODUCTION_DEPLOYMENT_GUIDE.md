# FINAL PRODUCTION DEPLOYMENT GUIDE

## Pre-requisites
1. Docker & Docker Compose
2. Minimum 4GB RAM Server (Ubuntu 22.04 LTS recommended)
3. Domain Name with SSL (Let's Encrypt / Cloudflare)

## 1. Secrets Management
The `.env` file must be strictly controlled and never committed to version control.
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://user:securepassword@db:5432/airisk
REDIS_URL=redis://redis:6379
JWT_SECRET=use-a-64-byte-secure-hex-string
```

## 2. Infrastructure Deployment
Run the following to start the production stack:
```bash
docker-compose -f docker-compose.yml up -d --build
```
This spins up:
- FastAPI Backend (Port 8000)
- Next.js Frontend (Port 3000)
- PostgreSQL (Database)
- Redis (EventBus and Idempotency)

## 3. Database Migrations
Always run Alembic to ensure the schema matches the production models:
```bash
docker-compose exec backend alembic upgrade head
```

## 4. HTTPS & Reverse Proxy
Expose the backend and frontend behind an NGINX reverse proxy.
- Ensure CORS in `app/core/config.py` is locked down to your specific frontend domains.
- Enforce `Strict-Transport-Security` headers.

## 5. Fallback & Scaling
- **Redis Failure:** If Redis crashes, the `ActionExecutor` fails safely and blocks autonomous transaction execution (Fail-Closed).
- **Postgres Failure:** Connection failures result in 500 errors but no unsafe state mutations occur.
- **Scaling:** The FastAPI backend is completely stateless (besides Redis) and can be horizontally scaled behind a load balancer.
