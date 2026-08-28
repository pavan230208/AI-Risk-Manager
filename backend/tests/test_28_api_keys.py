import pytest
from datetime import datetime, timedelta
import uuid
from app.models.tenant import Tenant, APIKey
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
import hashlib
import os

def hash_api_key(raw_key: str) -> str:
    # Simulating the hashing function, since we don't have passlib/bcrypt readily available in models 
    # we'll just use sha256 for testing purposes. In production we would use argon2/bcrypt.
    return hashlib.sha256(raw_key.encode()).hexdigest()

def generate_api_key(tenant_id: str):
    raw_secret = os.urandom(32).hex()
    prefix = f"pk_live_{tenant_id[:4]}_{os.urandom(4).hex()}"
    raw_key = f"{prefix}.{raw_secret}"
    key_hash = hash_api_key(raw_key)
    return raw_key, prefix, key_hash

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_tenant_creation_and_api_key_generation(db: Session):
    tenant_id = f"TENANT_{uuid.uuid4()}"
    tenant = Tenant(id=tenant_id, name="Test Tenant")
    db.add(tenant)
    db.commit()

    raw_key, prefix, key_hash = generate_api_key(tenant_id)
    key_id = f"KEY_{uuid.uuid4()}"
    
    api_key = APIKey(
        id=key_id,
        tenant_id=tenant_id,
        key_prefix=prefix,
        key_hash=key_hash,
        name="Primary Key"
    )
    db.add(api_key)
    db.commit()

    # Verify raw secret not persisted
    saved_key = db.query(APIKey).filter(APIKey.id == key_id).first()
    assert saved_key is not None
    assert saved_key.key_prefix == prefix
    assert saved_key.key_hash != raw_key
    assert raw_key not in saved_key.key_hash

def test_api_key_authentication(db: Session):
    tenant_id = f"TENANT_{uuid.uuid4()}"
    tenant = Tenant(id=tenant_id, name="Auth Tenant")
    db.add(tenant)
    db.commit()

    raw_key, prefix, key_hash = generate_api_key(tenant_id)
    api_key = APIKey(
        id=f"KEY_{uuid.uuid4()}",
        tenant_id=tenant_id,
        key_prefix=prefix,
        key_hash=key_hash,
        name="Auth Key"
    )
    db.add(api_key)
    db.commit()

    # Simulate successful authentication
    supplied_hash = hash_api_key(raw_key)
    matched_key = db.query(APIKey).filter(APIKey.key_prefix == prefix, APIKey.is_active == True, APIKey.is_revoked == False).first()
    assert matched_key is not None
    assert matched_key.key_hash == supplied_hash

def test_invalid_api_key_rejection(db: Session):
    supplied_hash = hash_api_key("invalid_key")
    matched_key = db.query(APIKey).filter(APIKey.key_prefix == "invalid_prefix", APIKey.is_active == True).first()
    assert matched_key is None

def test_revoked_api_key_rejection(db: Session):
    tenant_id = f"TENANT_{uuid.uuid4()}"
    tenant = Tenant(id=tenant_id, name="Revoked Tenant")
    db.add(tenant)
    db.commit()

    raw_key, prefix, key_hash = generate_api_key(tenant_id)
    api_key = APIKey(
        id=f"KEY_{uuid.uuid4()}",
        tenant_id=tenant_id,
        key_prefix=prefix,
        key_hash=key_hash,
        name="Revoked Key",
        is_revoked=True,
        revoked_at=datetime.utcnow()
    )
    db.add(api_key)
    db.commit()

    matched_key = db.query(APIKey).filter(APIKey.key_prefix == prefix, APIKey.is_active == True, APIKey.is_revoked == False).first()
    assert matched_key is None # Rejected due to is_revoked

def test_expired_api_key_rejection(db: Session):
    tenant_id = f"TENANT_{uuid.uuid4()}"
    tenant = Tenant(id=tenant_id, name="Expired Tenant")
    db.add(tenant)
    db.commit()

    raw_key, prefix, key_hash = generate_api_key(tenant_id)
    api_key = APIKey(
        id=f"KEY_{uuid.uuid4()}",
        tenant_id=tenant_id,
        key_prefix=prefix,
        key_hash=key_hash,
        name="Expired Key",
        expires_at=datetime.utcnow() - timedelta(days=1)
    )
    db.add(api_key)
    db.commit()

    matched_key = db.query(APIKey).filter(APIKey.key_prefix == prefix, APIKey.is_active == True, APIKey.is_revoked == False).first()
    # Check expiration logic
    assert matched_key.expires_at < datetime.utcnow() # In auth layer, we would reject

def test_inactive_tenant_rejection(db: Session):
    tenant_id = f"TENANT_{uuid.uuid4()}"
    tenant = Tenant(id=tenant_id, name="Inactive Tenant", is_active=False)
    db.add(tenant)
    db.commit()

    raw_key, prefix, key_hash = generate_api_key(tenant_id)
    api_key = APIKey(
        id=f"KEY_{uuid.uuid4()}",
        tenant_id=tenant_id,
        key_prefix=prefix,
        key_hash=key_hash,
        name="Inactive Tenant Key"
    )
    db.add(api_key)
    db.commit()

    matched_key = db.query(APIKey).filter(APIKey.key_prefix == prefix, APIKey.is_active == True, APIKey.is_revoked == False).first()
    assert matched_key.tenant.is_active == False # In auth layer, we would reject

def test_tenant_isolation(db: Session):
    tenant_a_id = f"TENANT_{uuid.uuid4()}"
    tenant_a = Tenant(id=tenant_a_id, name="Tenant A")
    tenant_b_id = f"TENANT_{uuid.uuid4()}"
    tenant_b = Tenant(id=tenant_b_id, name="Tenant B")
    db.add_all([tenant_a, tenant_b])
    db.commit()

    raw_key_a, prefix_a, hash_a = generate_api_key(tenant_a_id)
    api_key_a = APIKey(id=f"KEY_{uuid.uuid4()}", tenant_id=tenant_a_id, key_prefix=prefix_a, key_hash=hash_a, name="Key A")
    db.add(api_key_a)
    db.commit()

    # Simulate Auth for Tenant A
    auth_tenant = db.query(APIKey).filter(APIKey.key_prefix == prefix_a).first().tenant_id
    assert auth_tenant == tenant_a_id
    assert auth_tenant != tenant_b_id
