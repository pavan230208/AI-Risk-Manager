from typing import List, Optional
import os
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Autonomous AI Risk Manager"
    ENVIRONMENT: str = "development" # development, test, production
    DEBUG: bool = False
    
    # Request Size Limits
    MAX_REQUEST_SIZE_BYTES: int = 1048576 # Default 1MB
    
    # Base directory configurations
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str # Must be provided. E.g. postgresql://user:pass@host/db
    
    REDIS_URL: str
    
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_KEY: Optional[str] = None
    
    # LLM Settings
    LLM_PROVIDER: str = "mock" # options: openai, gemini, ollama, mock
    LLM_MODEL: str = "mock-model"
    LLM_API_KEY: Optional[str] = None

    @validator("JWT_SECRET")
    def validate_jwt_secret(cls, v: str, values: dict) -> str:
        env = values.get("ENVIRONMENT", "development")
        if env == "production" and len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long in production.")
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
