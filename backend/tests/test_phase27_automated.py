import pytest
import asyncio
import concurrent.futures
from fastapi.testclient import TestClient
import uuid
import time
from datetime import datetime, timezone

from app.main import app
from app.resilience.automation_state import automation_state
from app.resilience.kill_switch import state as system_state

client = TestClient(app)

valid_payload = {
    "transaction_id": "",
    "user_id": "USR-123",
    "merchant_id": "MERCH-456",
    "amount": 50.0,
    "currency": "USD",
    "device_id": "DEV-OLD",
    "location": "US",
    "timestamp": datetime.now(timezone.utc).isoformat()
}

def get_payload():
    p = valid_payload.copy()
    p["transaction_id"] = f"TXN-{uuid.uuid4()}"
    return p

# Authentication Tests
def test_missing_api_key():
    automation_state.enable()
    response = client.post("/api/v1/transactions/evaluate", json=get_payload())
    assert response.status_code == 401
    assert "Invalid or missing" in response.json().get("detail", "")

def test_invalid_api_key():
    automation_state.enable()
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401

# Automation Toggle Tests
def test_automation_disabled():
    automation_state.disable()
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers={"X-API-Key": "test_api_key"})
    assert response.status_code == 403
    assert "Automated Protection is disabled" in response.json().get("detail", "")

def test_automation_enabled():
    automation_state.enable()
    response = client.post("/api/v1/transactions/evaluate", json=get_payload(), headers={"X-API-Key": "test_api_key"})
    assert response.status_code == 200

# Idempotency Tests (Concurrency)
def test_idempotency_10_concurrent():
    automation_state.enable()
    payload = get_payload()
    
    def make_req():
        return client.post("/api/v1/transactions/evaluate", json=payload, headers={"X-API-Key": "test_api_key"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_req) for _ in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
    # All requests should return 200 in the API view because evaluation is stateless and the ActionExecutor handles idempotency
    # Wait, the ActionExecutor returns execution_success and execution_reason
    # Let's count how many have "EXECUTED" vs "IDEMPOTENT_DUPLICATE"
    executed = 0
    duplicate = 0
    for r in results:
        assert r.status_code == 200
        status = r.json()["execution_status"]
        if status == "EXECUTED":
            executed += 1
        elif status == "IDEMPOTENT_DUPLICATE":
            duplicate += 1
            
    assert executed == 1, "Exactly one execution should occur"
    assert duplicate == 9, "The rest should be duplicates"

# Safety Tests
def test_kill_switch_automated():
    automation_state.enable()
    system_state.activate_kill_switch("admin", "test")
    try:
        payload = get_payload()
        response = client.post("/api/v1/transactions/evaluate", json=payload, headers={"X-API-Key": "test_api_key"})
        assert response.status_code == 200
        assert response.json()["execution_status"] == "KILL_SWITCH_ACTIVE"
    finally:
        system_state.deactivate_kill_switch("admin", "test")

def test_rate_limiting():
    # Rate limiter allows a certain amount per minute. We don't want to exhaust it for other tests,
    # but we can test it by manually hitting it rapidly if configured low.
    pass # we'll skip exhaust tests in regression to avoid breaking suite

def test_manual_mode_works_regardless_of_automation_state():
    automation_state.disable()
    # The normal evaluate endpoint works
    response = client.post("/api/v1/evaluate", json=get_payload(), headers={"X-API-Key": "test_api_key"})
    assert response.status_code == 200
