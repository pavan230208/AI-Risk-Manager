from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

if settings.ENVIRONMENT == "production" and "sqlite" in settings.DATABASE_URL:
    raise RuntimeError("SQLite is not allowed in production. Use PostgreSQL.")

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
pool_args = {} if "sqlite" in settings.DATABASE_URL else {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **pool_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
