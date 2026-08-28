# FINAL PRODUCTION DEPLOYMENT PACKAGE

## 1. Target Cloud Architecture
**Recommendation: Option B (DigitalOcean App Platform + Managed Databases)**
- **Why?** It abstracts Kubernetes complexities away from students/hackathons while natively providing HTTPS out-of-the-box. It provides straightforward, managed deployment of Python/Node apps, PostgreSQL, and Redis within a secure, private VPC network at a highly predictable monthly cost that fits hackathon grants. 

## 2. Secrets Checklist
These must be securely injected via the DigitalOcean Environment Variables console, and NOT pushed in code.
- [ ] `ENVIRONMENT=production`
- [ ] `JWT_SECRET` (Cryptographically secure 64-byte string)
- [ ] `DATABASE_URL` (DO Managed PostgreSQL Connection URI)
- [ ] `REDIS_URL` (DO Managed Redis Connection URI)

## 3. Deployment Commands & Procedures

### Step 1: Database Migration
This should be executed as a "Pre-Deploy" Job in DigitalOcean:
```bash
cd backend
alembic upgrade head
```
*If this fails, the deployment halts. This prevents code/schema desynchronization.*

### Step 2: Backend Container (FastAPI)
**Build Command:** (Docker natively handles this)
**Run Command:**
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```
*Ensure CORS is locked to your frontend's specific production URL via config modifications before deploying.*

### Step 3: Frontend Container (Next.js)
**Build Command:**
```bash
npm run build
```
**Run Command:**
```bash
npm start
```
*Inject `NEXT_PUBLIC_API_URL` pointing to the public URL of the deployed FastAPI component.*

## 4. Rollback & Disaster Recovery
- **Rollback:** In DO App Platform, revert to the previous successful commit hash via the deployment timeline UI.
- **Backup:** DigitalOcean Managed PostgreSQL automatically handles daily snapshots. Redis state (Locks, EventBus) is ephemeral and non-critical for long-term disaster recovery.
