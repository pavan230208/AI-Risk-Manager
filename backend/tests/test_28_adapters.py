import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.resilience.automation_state import automation_state

client = TestClient(app)

def test_webhook_generic():
    automation_state.enable()
    payload = {
        "transaction_id": "generic-1",
        "user_id": "u1",
        "merchant_id": "m1",
        "amount": 100.0,
        "currency": "USD",
        "device_id": "d1",
        "location": "loc",
        "timestamp": "2023-01-01T00:00:00Z"
    }
    resp = client.post("/api/v1/webhooks/transactions?provider=generic", json=payload, headers={"X-API-Key": "test_api_key"})
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "generic-1"

def test_webhook_razorpay():
    automation_state.enable()
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_rzp1",
                    "amount": 50000,
                    "currency": "INR",
                    "customer_id": "cust1"
                }
            }
        }
    }
    resp = client.post("/api/v1/webhooks/transactions?provider=razorpay", json=payload, headers={"X-API-Key": "test_api_key"})
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "pay_rzp1"

def test_webhook_upi():
    automation_state.enable()
    payload = {
        "txnId": "upi_txn_1",
        "payerVpa": "u@upi",
        "payeeVpa": "m@upi",
        "amount": "100.00"
    }
    resp = client.post("/api/v1/webhooks/transactions?provider=upi", json=payload, headers={"X-API-Key": "test_api_key"})
    assert resp.status_code == 200
    assert resp.json()["transaction_id"] == "upi_txn_1"

def test_webhook_invalid_payload():
    automation_state.enable()
    # Razorpay payload missing payment entity
    payload = {"event": "payment.captured"}
    resp = client.post("/api/v1/webhooks/transactions?provider=razorpay", json=payload, headers={"X-API-Key": "test_api_key"})
    assert resp.status_code == 422
    assert "Provider normalization failed" in resp.json()["detail"]
