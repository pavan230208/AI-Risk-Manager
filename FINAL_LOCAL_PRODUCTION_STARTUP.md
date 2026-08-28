# FINAL LOCAL PRODUCTION STARTUP GUIDE

This guide explains how to start the Autonomous AI Risk Manager in a local production-like environment for demonstration purposes.

## 1. Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+

## 2. Environment Configuration
Ensure your `backend/.env` file is populated with production defaults. You can copy `.env.example`:
```bash
cp .env.example backend/.env
```
Make sure `ENVIRONMENT=production` and `USE_FAKEREDIS=0` in this file.

## 3. Docker Startup
Start the required PostgreSQL and Redis infrastructure:
```bash
docker compose up -d
```
Verify they are running:
```bash
docker compose ps
```

## 4. Database Migration
Initialize the PostgreSQL schema using Alembic:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
```

## 5. Backend Startup
Start the FastAPI server:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 6. Frontend Startup
Open a new terminal, install dependencies, build, and start the Next.js UI:
```bash
cd frontend
npm ci
npm run build
npm run start
```

## 7. Health Verification
Open your browser and navigate to:
- `http://localhost:8000/health/liveness`
- `http://localhost:8000/health/readiness`
Both should return success messages indicating connections to Postgres and Redis are healthy.

## 8. Demo Execution
Open `http://localhost:3000` in your web browser. Follow the provided scenario buttons (SAFE, SUSPICIOUS, CRITICAL) to evaluate transactions and view the System Trace.

## 9. Shutdown Procedure
To gracefully stop the application:
1. Terminate the frontend process (`Ctrl+C`).
2. Terminate the backend process (`Ctrl+C`).
3. Spin down the Docker infrastructure:
```bash
docker compose down
```
*(Use `docker compose down -v` if you wish to wipe the database entirely).*

## 10. Troubleshooting
- **Port Conflicts**: Ensure ports `8000` (FastAPI), `3000` (Next.js), `5432` (Postgres), and `6379` (Redis) are free.
- **CORS Errors**: Verify that `BACKEND_CORS_ORIGINS=["http://localhost:3000"]` is correctly set in `backend/.env`.
- **Database Connection Issues**: Verify the `DATABASE_URL` matches the credentials used in `docker-compose.yml`.
