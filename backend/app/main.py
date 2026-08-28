from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="Autonomous AI Risk Manager API",
    description="Backend API for managing transactions, AI risks, and autonomous operations.",
    version="1.0.0",
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
    )

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > settings.MAX_REQUEST_SIZE_BYTES:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": f"Request body too large. Max size is {settings.MAX_REQUEST_SIZE_BYTES} bytes."}
                )
    return await call_next(request)

from app.api.router import router

@app.get("/health/liveness")
def liveness():
    return {"status": "alive"}

@app.get("/health/readiness")
def readiness():
    from app.actions.executor import ActionExecutor
    from app.db.database import engine
    from sqlalchemy import text
    
    status_code = 200
    checks = {"api": "ok", "redis": "failed", "postgres": "failed"}
    
    # Check Postgres
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        status_code = 503
        
    # Check Redis
    try:
        r = ActionExecutor()._get_redis()
        if r and r.ping():
            checks["redis"] = "ok"
        else:
            status_code = 503
    except Exception:
        status_code = 503
        
    from fastapi import Response
    return Response(content=str(checks), status_code=status_code)

app.include_router(router, prefix="/api/v1")

