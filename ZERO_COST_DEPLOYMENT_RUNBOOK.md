# ZERO-COST DEPLOYMENT RUNBOOK

This runbook outlines the architecture for deploying the Autonomous AI Risk Manager using entirely free-tier services, requiring no credit card and incurring zero costs, while maintaining the required production architecture (FastAPI + Next.js + Real Postgres + Real Redis).

## 1. Zero-Cost Cloud Architecture

### **Database (PostgreSQL 15): Neon or Supabase**
- **Service:** Neon.tech (Serverless Postgres) or Supabase.
- **Free Tier Limits:** 500MB storage, 1 project, sufficient compute for hackathon loads.
- **Why:** True free tier, instant provisioning, provides a standard `postgres://` connection string.

### **Cache & EventBus (Redis 7): Upstash**
- **Service:** Upstash (Serverless Redis).
- **Free Tier Limits:** 10,000 commands per day, max 256MB size.
- **Why:** True free tier, no credit card required, provides a standard `rediss://` (TLS) connection string. Perfectly handles Idempotency locks and EventBus for demo scale.

### **Backend (FastAPI): Render**
- **Service:** Render (Web Service).
- **Free Tier Limits:** 512 MB RAM, spins down after 15 minutes of inactivity (cold start takes ~30 seconds).
- **Why:** Native Dockerfile support, free HTTPS, easy environment variable injection. (Alternative: Koyeb).

### **Frontend (Next.js): Vercel**
- **Service:** Vercel.
- **Free Tier Limits:** Hobby tier (Free), native Next.js optimization.
- **Why:** Instant deployments from GitHub, free HTTPS, global CDN.

---

## 2. Environment Variables & Secret Configuration
Inject these into Render (Backend) and Vercel (Frontend):

**Backend (Render Secrets):**
```env
ENVIRONMENT=production
DATABASE_URL=postgresql://[user]:[password]@[neon-host].neon.tech/neondb?sslmode=require
REDIS_URL=rediss://default:[password]@[upstash-host].upstash.io:32616
JWT_SECRET=generate-a-secure-64-byte-string-locally
```

**Frontend (Vercel Environment Variables):**
```env
NEXT_PUBLIC_API_URL=https://your-backend-app.onrender.com
```

---

## 3. Database Migration Strategy
On Render, you can specify a "Build Command" or "Start Command". 
To ensure migrations run safely on the free tier:
**Render Start Command:**
```bash
alembic upgrade head && gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT
```
*(Note: Worker count is reduced to 1 to fit comfortably inside Render's 512MB RAM free tier limit).*

## 4. Limitations & Caveats of Free Tiers
- **Cold Starts:** Render's free tier spins down the backend after 15 minutes of inactivity. The first API request after this will take 30-60 seconds to resolve. (Tip for demo: Keep the backend awake by hitting it right before presenting).
- **Rate Limits:** Upstash limits to 10k commands/day. The frontend System Trace polls Redis frequently. For a live environment, you may need to increase the polling interval in the UI (e.g., from 1s to 5s) to avoid exhausting the free Upstash quota quickly during prolonged testing.
