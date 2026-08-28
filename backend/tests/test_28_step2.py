import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.models.tenant import Tenant, APIKey
from app.models.transaction import Transaction
from app.resilience.automation_state import automation_state
import uuid
import hashlib
from datetime import datetime, timedelta, timezone

client = TestClient(app)

def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()

def generate_key_pair(tenant_id: str):
    import os
    raw_secret = os.urandom(16).hex()
    prefix = f"pk_live_{tenant_id[:4]}_{os.urandom(2).hex()}"
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

@pytest.fixture
def setup_tenants(db):
    t_a_id = f"TENANT_A_{uuid.uuid4()}"
    t_b_id = f"TENANT_B_{uuid.uuid4()}"
    
    tenant_a = Tenant(id=t_a_id, name="Tenant A")
    tenant_b = Tenant(id=t_b_id, name="Tenant B")
    db.add_all([tenant_a, tenant_b])
    db.commit()
    
    key_a_raw, prefix_a, hash_a = generate_key_pair(t_a_id)
    key_b_raw, prefix_b, hash_b = generate_key_pair(t_b_id)
    
    api_key_a = APIKey(id=f"KEY_{uuid.uuid4()}", tenant_id=t_a_id, key_prefix=prefix_a, key_hash=hash_a, name="Key A")
    api_key_b = APIKey(id=f"KEY_{uuid.uuid4()}", tenant_id=t_b_id, key_prefix=prefix_b, key_hash=hash_b, name="Key B")
    db.add_all([api_key_a, api_key_b])
    db.commit()
    
    return {
        "tenant_a": t_a_id, "key_a_raw": key_a_raw,
        "tenant_b": t_b_id, "key_b_raw": key_b_raw
    }

def get_payload():
    return {
        "transaction_id": f"TXN-{uuid.uuid4()}",
        "user_id": "USR-123",
        "merchant_id": "MERCH-456",
        "amount": 50.0,
        "currency": "USD",
        "device_id": "DEV-1",
        "location": "US",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def test_tenant_a_valid_api_key(setup_tenants):
    automation_state.enable()
    headers = {"X-API-Key": setup_tenants["key_a_raw"]}
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers=headers)
    assert response.status_code == 200
    assert response.json()["tenant_id"] == setup_tenants["tenant_a"]

def test_tenant_b_valid_api_key(setup_tenants):
    automation_state.enable()
    headers = {"X-API-Key": setup_tenants["key_b_raw"]}
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers=headers)
    assert response.status_code == 200
    assert response.json()["tenant_id"] == setup_tenants["tenant_b"]

def test_revoked_key(setup_tenants, db):
    # Revoke key A
    key = db.query(APIKey).filter(APIKey.tenant_id == setup_tenants["tenant_a"]).first()
    key.is_revoked = True
    db.commit()
    
    headers = {"X-API-Key": setup_tenants["key_a_raw"]}
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers=headers)
    assert response.status_code == 401

def test_expired_key(setup_tenants, db):
    key = db.query(APIKey).filter(APIKey.tenant_id == setup_tenants["tenant_a"]).first()
    key.expires_at = datetime.utcnow() - timedelta(days=1)
    db.commit()
    
    headers = {"X-API-Key": setup_tenants["key_a_raw"]}
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers=headers)
    assert response.status_code == 401

def test_invalid_key():
    headers = {"X-API-Key": "invalid.key"}
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers=headers)
    assert response.status_code == 401
