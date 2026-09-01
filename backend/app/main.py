from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.api.router import router

setup_logging()

app = FastAPI(
    title="Autonomous AI Risk Manager API",
    description="Backend API for managing transactions, AI risks, and autonomous operations.",
    version="1.0.0",
)

@app.middleware("http")
async def cors_and_limit_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=200)

    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_REQUEST_SIZE_BYTES:
            res = JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"Request body too large. Max size is {settings.MAX_REQUEST_SIZE_BYTES} bytes."}
            )
            return res

    response = await call_next(request)
    return response

origins = [
    "https://ai-risk-manager-delta.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost",
]

if settings.BACKEND_CORS_ORIGINS:
    origins.extend([str(origin) for origin in settings.BACKEND_CORS_ORIGINS])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

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

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        status_code = 503

    try:
        r = ActionExecutor()._get_redis()
        if r and r.ping():
            checks["redis"] = "ok"
        else:
            status_code = 503
    except Exception:
        status_code = 503

    return Response(content=str(checks), status_code=status_code)

app.include_router(router, prefix="/api/v1")
