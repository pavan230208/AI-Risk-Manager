# FINAL DEMO CHECKLIST

Follow this checklist immediately before any presentation, seminar, or buildathon demo.

## 1. Environment Verification
- [ ] `.env` file is present in `backend/` and configured with `ENVIRONMENT=production`.
- [ ] `USE_FAKEREDIS=0` is set to ensure real Redis is used.
- [ ] No actual secrets are checked into version control.

## 2. Infrastructure Initialization
- [ ] Run `docker compose down -v` to ensure a clean slate.
- [ ] Run `docker compose up -d` to start PostgreSQL and Redis.
- [ ] Verify containers are healthy (`docker compose ps`).
- [ ] Run database migrations: `cd backend && alembic upgrade head`.

## 3. Backend Verification
- [ ] Start the backend server: `cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- [ ] Verify health endpoint in browser: `http://localhost:8000/health/liveness` returns `{"status": "alive"}`.
- [ ] Verify readiness endpoint in browser: `http://localhost:8000/health/readiness` returns all `ok`.

## 4. Frontend Verification
- [ ] Start the frontend: `cd frontend && npm run start`.
- [ ] Open `http://localhost:3000` in a fresh browser window.
- [ ] Ensure the browser console shows no CORS errors.

## 5. Scenario Rehearsal
- [ ] **SAFE Scenario**: Click 'SAFE' -> Analyze. Ensure score is low and status is EXECUTED.
- [ ] **SUSPICIOUS Scenario**: Click 'SUSPICIOUS' -> Analyze. Ensure it's flagged and BLOCKED.
- [ ] **CRITICAL Scenario**: Click 'CRITICAL' -> Analyze. Ensure it's fully BLOCKED due to rules.
- [ ] **Duplicate Attack**: Double-click 'Analyze' rapidly on the same transaction. Ensure UI shows "Duplicate execution prevented".
- [ ] **Kill Switch**: Activate Kill Switch. Run a 'SAFE' transaction. Ensure it blocks. Deactivate Kill Switch.
- [ ] **System Trace**: Open trace view. Verify events populated cleanly with no exposed secrets.

## 6. Emergency Recovery
- [ ] If demo locks up, hard refresh the browser (F5).
- [ ] If backend hangs, restart the Uvicorn process.
- [ ] If data is corrupt, run `docker compose down -v` and restart the checklist.
