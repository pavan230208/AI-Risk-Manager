import jwt
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from typing import List
from enum import Enum
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.tenant import APIKey
import hashlib
from datetime import datetime, timezone

class Role(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

security = HTTPBearer(auto_error=False)

def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_roles(allowed_roles: List[Role]):
    def role_checker(payload: dict = Depends(verify_jwt_token)):
        user_role = payload.get("role")
        if not user_role:
            raise HTTPException(status_code=403, detail="Role claim missing in token")
        
        if user_role not in [r.value for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        return payload
    return role_checker

from fastapi.security import APIKeyHeader
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Depends(api_key_header)):
    if settings.ENVIRONMENT == "production":
        if not api_key or api_key != settings.API_KEY:
            raise HTTPException(
                status_code=401,
                detail="Invalid API Key"
            )
    return api_key

def verify_integration_api_key(api_key: str = Depends(api_key_header), db: Session = Depends(get_db)):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header"
        )
        
    # Legacy compatibility check (remove later)
    if api_key == settings.API_KEY:
        # In production, legacy key is not mapped to a tenant, it's global
        # but the spec requires tenant_id for new transactions. 
        # We return a legacy tenant context or None.
        return {"tenant_id": None, "legacy": True}

    parts = api_key.split(".")
    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid API Key format")
    
    prefix = parts[0]
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    matched_key = db.query(APIKey).filter(APIKey.key_prefix == prefix).first()
    
    if not matched_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    if matched_key.key_hash != key_hash:
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    if not matched_key.is_active or matched_key.is_revoked:
        raise HTTPException(status_code=401, detail="API Key revoked or inactive")
        
    if matched_key.expires_at and matched_key.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="API Key expired")
        
    if not matched_key.tenant.is_active:
        raise HTTPException(status_code=401, detail="Tenant is inactive")
        
    # Optional: Update last_used_at async or background task
    # matched_key.last_used_at = datetime.utcnow()
    # db.commit()
    
    return {"tenant_id": matched_key.tenant_id, "api_key_id": matched_key.id, "legacy": False}
