import pytest
from fastapi.testclient import TestClient
from app.main import app
import os
import json
import jwt
from datetime import datetime, timezone, timedelta
from app.core.config import settings

def get_admin_token():
    payload = {
        "sub": "admin",
        "role": "ADMIN",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

os.environ["USE_FAKEREDIS"] = "1"

client = TestClient(app)

def test_evaluate_endpoint():
    payload = {
        "transaction_id": "TXN-TEST-123",
        "user_id": "USR-1",
        "merchant_id": "MERCH-1",
        "amount": 25.0,
        "currency": "USD",
        "device_id": "DEV-1",
        "location": "US",
        "timestamp": "2026-08-25T12:00:00Z"
    }
    
    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["transaction_id"] == "TXN-TEST-123"
    assert "ml_probability" in data
    assert "risk_level" in data
    assert "policy_action" in data
    assert "execution_status" in data
    assert "correlation_id" in data

def test_system_trace_endpoint():
    headers = {"Authorization": f"Bearer {get_admin_token()}"}
    response = client.get("/api/v1/system/trace", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "system_state" in data
    assert "redis_status" in data

def test_kill_switch_endpoint():
    headers = {"Authorization": f"Bearer {get_admin_token()}"}
    response = client.post("/api/v1/system/kill-switch", json={"active": True}, headers=headers)
    assert response.status_code == 200
    assert response.json()["kill_switch_active"] == True
    
    response2 = client.get("/api/v1/system/trace", headers=headers)
    assert response2.json()["system_state"] == "AUTONOMOUS_ACTIONS_DISABLED"
    
    # reset
    client.post("/api/v1/system/kill-switch", json={"active": False}, headers=headers)
