import pytest
from fastapi.testclient import TestClient
import jwt
from datetime import datetime, timezone, timedelta
from app.main import app
from app.core.config import settings
from app.api.auth import Role

client = TestClient(app)

def create_token(role: str, user_id: str = "test_user", expire_delta: timedelta = timedelta(minutes=30), secret: str = settings.JWT_SECRET):
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + expire_delta
    }
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)

def test_missing_jwt():
    response = client.get("/api/v1/system/trace")
    assert response.status_code == 401

def test_invalid_jwt():
    response = client.get("/api/v1/system/trace", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]

def test_expired_jwt():
    token = create_token(Role.ADMIN, expire_delta=timedelta(minutes=-10))
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]

def test_wrong_signing_secret():
    token = create_token(Role.ADMIN, secret="WRONG_SECRET")
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_valid_admin_access():
    token = create_token(Role.ADMIN)
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_valid_analyst_access():
    token = create_token(Role.ANALYST)
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_valid_operator_access():
    token = create_token(Role.OPERATOR)
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_valid_viewer_access():
    token = create_token(Role.VIEWER)
    response = client.get("/api/v1/system/trace", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_analyst_attempting_admin_operation():
    token = create_token(Role.ANALYST)
    response = client.post("/api/v1/system/kill-switch", json={"active": True}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]

def test_operator_attempting_admin_operation():
    token = create_token(Role.OPERATOR)
    response = client.post("/api/v1/system/kill-switch", json={"active": True}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert "Insufficient permissions" in response.json()["detail"]

def test_viewer_attempting_state_changing_operation():
    token = create_token(Role.VIEWER)
    response = client.post("/api/v1/system/kill-switch", json={"active": True}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

def test_unauthorized_kill_switch_activation():
    # No auth
    response = client.post("/api/v1/system/kill-switch", json={"active": True})
    assert response.status_code == 401

def test_unauthorized_kill_switch_deactivation():
    # No auth
    response = client.post("/api/v1/system/kill-switch", json={"active": False})
    assert response.status_code == 401

def test_valid_admin_kill_switch_activation():
    token = create_token(Role.ADMIN)
    response = client.post("/api/v1/system/kill-switch", json={"active": True}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["kill_switch_active"] is True
    
    # Deactivate for cleanup
    response = client.post("/api/v1/system/kill-switch", json={"active": False}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
