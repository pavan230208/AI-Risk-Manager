import os
os.environ["ENVIRONMENT"] = "production"
os.environ["JWT_SECRET"] = "this_is_a_very_long_and_secure_jwt_secret_for_production"
os.environ["EVENT_BUS_BACKEND"] = "redis"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["DATABASE_URL"] = "postgresql://postgres:password@localhost:5432/risk_manager"
os.environ["MAX_REQUEST_SIZE_BYTES"] = "1048576"
os.environ["USE_FAKEREDIS"] = "0"

os.environ["API_KEY"] = "this_is_a_secure_api_key"

from fastapi.testclient import TestClient
from app.main import app
import jwt
from datetime import datetime, timezone, timedelta
import uuid

client = TestClient(app)

print("--- HEALTH ---")
print("Liveness:", client.get("/health/liveness").text)
print("Readiness:", client.get("/health/readiness").text)

print("\n--- AUTHENTICATION ---")
def get_token(role):
    payload = {"sub": "user123", "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")

headers = {"Authorization": f"Bearer {get_token('ADMIN')}"}
api_headers = {"X-API-Key": "this_is_a_secure_api_key"}
print("No token:", client.get("/api/v1/system/trace").status_code)
print("Invalid token:", client.get("/api/v1/system/trace", headers={"Authorization": "Bearer invalid"}).status_code)

print("\n--- TRANSACTION PIPELINE ---")
tx = {
    "transaction_id": str(uuid.uuid4()),
    "user_id": "U1",
    "merchant_id": "M1",
    "amount": 20.0,
    "currency": "USD",
    "device_id": "D1",
    "location": "US",
    "timestamp": datetime.now(timezone.utc).isoformat()
}
res = client.post("/api/v1/evaluate", json=tx, headers=api_headers)
if res.status_code == 200:
    print("SAFE Transaction:", res.status_code, res.json().get("risk_level"), res.json().get("policy_action"), res.json().get("execution_status"))
else:
    print("SAFE Transaction Failed:", res.status_code, res.text)

tx["amount"] = 50000.0
res = client.post("/api/v1/evaluate", json=tx, headers=api_headers)
if res.status_code == 200:
    print("CRITICAL Transaction:", res.status_code, res.json().get("risk_level"), res.json().get("policy_action"), res.json().get("execution_status"))
else:
    print("CRITICAL Transaction Failed:", res.status_code, res.text)

print("\n--- KILL SWITCH ---")
ks_res = client.post("/api/v1/system/kill-switch", json={"active": True}, headers=headers)
if ks_res.status_code == 200:
    print("Kill Switch Activated:", ks_res.json())
else:
    print("Kill Switch Failed:", ks_res.status_code, ks_res.text)

tx["amount"] = 20.0
tx["transaction_id"] = str(uuid.uuid4())
res = client.post("/api/v1/evaluate", json=tx, headers=api_headers)
if res.status_code == 200:
    print("SAFE Transaction with KS ON:", res.json().get("execution_status"))
else:
    print("SAFE Transaction with KS ON Failed:", res.status_code, res.text)
client.post("/api/v1/system/kill-switch", json={"active": False}, headers=headers)

print("\n--- EVENT TRACE ---")
trace = client.get("/api/v1/system/trace", headers=headers)
if trace.status_code == 200:
    print("Trace Recent Events:", len(trace.json().get("recent_events", [])))
    print("Trace System State:", trace.json().get("system_state"))
else:
    print("Trace Failed:", trace.status_code, trace.text)
