import pytest
from app.actions.executor import ActionExecutor
import os
import uuid
import threading
import time
from datetime import datetime, timezone, timedelta
import json

@pytest.fixture
def executor():
    os.environ["USE_FAKEREDIS"] = "1"
    os.environ["ACTION_LEASE_SECONDS"] = "2"
    os.environ["ACTION_MAX_LEASE_SECONDS"] = "4"
    return ActionExecutor()

def test_duplicate_execution_race_condition(executor):
    action_id = str(uuid.uuid4())
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": action_id,
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED"
    }
    
    results = []
    
    def worker():
        success, reason = executor.execute(req)
        results.append((success, reason))
        
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    successes = [r for r in results if r[0] is True]
    assert len(successes) == 1, "Exactly one executor should succeed"
    assert len(results) == 5

def test_lease_expiration_takeover(executor):
    r = executor._get_redis()
    action_id = str(uuid.uuid4())
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": action_id,
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED",
        "mock_lose_lease": True  # Instructs execute() to backdate the lease inside
    }
    
    success, reason = executor.execute(req)
    assert success is False
    assert reason == "EXECUTED_BUT_LOST_LEASE"
    
    # State should be RECONCILIATION_REQUIRED
    raw = r.get(f"action_exec:{action_id}")
    assert raw is not None
    record = json.loads(raw)
    assert record["executor_state"] == "RECONCILIATION_REQUIRED"

def test_redis_unavailable():
    os.environ["USE_FAKEREDIS"] = "0"
    executor_fail = ActionExecutor(redis_url="redis://nonexistent:6379/0")
    
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED"
    }
    success, reason = executor_fail.execute(req)
    assert success is False
    assert reason == "IDEMPOTENCY_UNAVAILABLE"

def test_downstream_timeout(executor):
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED",
        "mock_downstream_timeout": True
    }
    success, reason = executor.execute(req)
    assert success is False
    assert reason == "RECONCILIATION_REQUIRED"
    
    raw = executor._get_redis().get(f"action_exec:{req['action_id']}")
    record = json.loads(raw)
    assert record["executor_state"] == "RECONCILIATION_REQUIRED"

def test_expired_authorization(executor):
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    }
    success, reason = executor.execute(req)
    assert success is False
    assert reason == "EXPIRED"

def test_unauthorized_execution(executor):
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "PENDING_APPROVAL",
    }
    success, reason = executor.execute(req)
    assert success is False
    assert reason == "HUMAN_APPROVAL_REQUIRED"

def test_kill_switch_blocks_execution(executor):
    from app.resilience.kill_switch import state
    state.activate_kill_switch("test", "test")
    
    req = {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "transaction_id": "TX-1",
        "action_type": "ALLOW",
        "version": "1.0.0",
        "authorization_state": "AUTHORIZED",
    }
    success, reason = executor.execute(req)
    
    state.deactivate_kill_switch("test", "test")
    
    assert success is False
    assert reason == "KILL_SWITCH_ACTIVE"
