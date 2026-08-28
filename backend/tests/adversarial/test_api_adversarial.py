import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_negative_amount_rejected():
    payload = {
        "transaction_id": "TXN-1",
        "user_id": "USR-1",
        "merchant_id": "MERCH-1",
        "amount": -100.0,
        "currency": "USD",
        "device_id": "DEV-1",
        "location": "US",
        "timestamp": "2026-08-25T12:00:00Z"
    }
    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code == 422
    assert "Amount cannot be negative" in response.text or "greater than or equal to 0" in response.text

def test_missing_fields_rejected():
    payload = {
        "transaction_id": "TXN-1"
    }
    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code == 422
    assert "Field required" in response.text

def test_invalid_currency_rejected():
    payload = {
        "transaction_id": "TXN-1",
        "user_id": "USR-1",
        "merchant_id": "MERCH-1",
        "amount": 100.0,
        "currency": "USD_INVALID",
        "device_id": "DEV-1",
        "location": "US",
        "timestamp": "2026-08-25T12:00:00Z"
    }
    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code == 422
