import os
import pytest
import uuid
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import Dict

# Ensure we do NOT use fakeredis
os.environ["USE_FAKEREDIS"] = "0"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.actions.executor import ActionExecutor
from app.resilience.kill_switch import state as system_state

def get_base_payload() -> Dict:
    return {
        "action_id": f"act_{uuid.uuid4()}",
        "transaction_id": f"tx_{uuid.uuid4()}",
        "action_type": "BLOCK_MERCHANT",
        "version": "1.0",
        "authorization_state": "AUTHORIZED",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    }

def test_real_redis_connectivity():
    executor = ActionExecutor()
    r = executor._get_redis()
    assert r is not None, "Real Redis must be reachable"
    assert r.ping() is True

def test_idempotency_duplicate_execution():
    executor = ActionExecutor()
    payload = get_base_payload()
    
    # First execution should succeed
    success, reason = executor.execute(payload)
    assert success is True
    assert reason == "EXECUTED"
    
    # Second execution should fail
    success, reason = executor.execute(payload)
    assert success is False
    assert reason == "IDEMPOTENT_DUPLICATE"

def test_concurrency_race_condition():
    executor = ActionExecutor()
    payload = get_base_payload()
    
    def attempt_exec():
        return executor.execute(payload)
        
    results = []
    # Use threads to hit Redis concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as tp:
        futures = [tp.submit(attempt_exec) for _ in range(10)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
            
    successes = [r for r in results if r[0] is True]
    assert len(successes) == 1, "Only one execution should succeed"
    assert successes[0][1] == "EXECUTED"

def test_stale_executor_cannot_renew():
    executor = ActionExecutor()
    # Mocking redis direct to set a fake token
    r = executor._get_redis()
    action_id = f"act_{uuid.uuid4()}"
    idem_key = f"action_exec:{action_id}"
    
    # Create record with a different token
    import json
    record = {
        "execution_token": "valid_token",
        "executor_state": "EXECUTING",
        "lease_started_at": datetime.now(timezone.utc).isoformat()
    }
    r.set(idem_key, json.dumps(record))
    
    # Attempt to renew with a stale/invalid token
    renewed = executor.renew_lease(action_id, "stale_token")
    assert renewed is False

def test_lease_expiration_and_terminal_state():
    # If state is EXECUTED, it shouldn't be renewed
    executor = ActionExecutor()
    r = executor._get_redis()
    action_id = f"act_{uuid.uuid4()}"
    idem_key = f"action_exec:{action_id}"
    
    import json
    token = str(uuid.uuid4())
    record = {
        "execution_token": token,
        "executor_state": "EXECUTED",
        "lease_started_at": datetime.now(timezone.utc).isoformat()
    }
    r.set(idem_key, json.dumps(record))
    
    renewed = executor.renew_lease(action_id, token)
    assert renewed is False, "Cannot renew terminal state"

def test_unknown_result_requires_reconciliation():
    executor = ActionExecutor()
    payload = get_base_payload()
    payload["mock_downstream_timeout"] = True
    
    success, reason = executor.execute(payload)
    assert success is False
    assert reason == "RECONCILIATION_REQUIRED"
    
    # Next attempt should fail immediately because it's in RECONCILIATION_REQUIRED
    success, reason = executor.execute(payload)
    assert success is False
    assert reason == "RECONCILIATION_REQUIRED"

def test_kill_switch_blocks_execution():
    executor = ActionExecutor()
    payload = get_base_payload()
    
    system_state.activate_kill_switch("test_admin", "Testing")
    try:
        success, reason = executor.execute(payload)
        assert success is False
        assert reason == "KILL_SWITCH_ACTIVE"
    finally:
        system_state.deactivate_kill_switch("test_admin", "Testing")

def test_unauthorized_state():
    executor = ActionExecutor()
    payload = get_base_payload()
    payload["authorization_state"] = "PENDING_APPROVAL"
    
    success, reason = executor.execute(payload)
    assert success is False
    assert reason == "HUMAN_APPROVAL_REQUIRED"
    
    payload["authorization_state"] = "DENIED"
    success, reason = executor.execute(payload)
    assert success is False
    assert reason == "UNAUTHORIZED_STATE"

def test_lease_renewal_flow():
    executor = ActionExecutor()
    # Set lease to very short duration to test expiration logic
    executor.initial_lease_seconds = 1
    executor.max_lease_seconds = 5
    
    payload = get_base_payload()
    action_id = payload["action_id"]
    r = executor._get_redis()
    
    # Let's bypass execute logic and just put an EXECUTING token in Redis to test renewal
    token = "test_token"
    import json
    now = datetime.now(timezone.utc)
    record = {
        "execution_token": token,
        "executor_state": "EXECUTING",
        "lease_started_at": now.isoformat(),
        "lease_expires_at": (now + timedelta(seconds=2)).isoformat()
    }
    r.set(f"action_exec:{action_id}", json.dumps(record))
    
    # 1. Valid renewal
    assert executor.renew_lease(action_id, token) is True
    
    # 2. Let it expire
    time.sleep(2.1)
    
    # 3. Renew after lease expiry - the Lua script actually doesn't check lease expiry itself during update?
    # Wait, the `_atomic_update` method explicitly checks:
    # `if now > expires_at: return False`
    assert executor.renew_lease(action_id, token) is False
