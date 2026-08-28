import pytest
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from app.actions.executor import ActionExecutor

os.environ["USE_FAKEREDIS"] = "1"

@pytest.fixture
def executor():
    return ActionExecutor()

@pytest.fixture
def valid_action():
    return {
        "event_id": str(uuid.uuid4()),
        "action_id": str(uuid.uuid4()),
        "correlation_id": str(uuid.uuid4()),
        "transaction_id": "TX-12345",
        "action_type": "BLOCK",
        "version": "1.0",
        "authorization_state": "AUTHORIZED",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    }

def test_missing_action_id(executor, valid_action):
    del valid_action["action_id"]
    del valid_action["event_id"]
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "MISSING_ACTION_ID"

def test_idempotency_unavailable(valid_action):
    # Mocking redis unavailability
    executor = ActionExecutor()
    executor.redis = None
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "IDEMPOTENCY_UNAVAILABLE"

def test_unknown_action(executor, valid_action):
    valid_action["action_type"] = "UNKNOWN"
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "UNKNOWN_ACTION"

def test_malformed_authorization(executor, valid_action):
    del valid_action["transaction_id"]
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "MALFORMED_AUTHORIZATION"

def test_invalid_policy_version(executor, valid_action):
    valid_action["version"] = "2.0"
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "INVALID_POLICY_VERSION"

def test_human_approval_required(executor, valid_action):
    valid_action["authorization_state"] = "PENDING_APPROVAL"
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "HUMAN_APPROVAL_REQUIRED"

def test_unauthorized_state(executor, valid_action):
    valid_action["authorization_state"] = "REJECTED"
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "UNAUTHORIZED_STATE"

def test_expired_authorization(executor, valid_action):
    valid_action["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "EXPIRED"

def test_valid_execution_and_idempotency(executor, valid_action):
    # Scenario A: Same action_id on same executor
    success, reason = executor.execute(valid_action)
    assert success
    assert reason == "EXECUTED"
    
    # Try again
    success2, reason2 = executor.execute(valid_action)
    assert not success2
    assert reason2 == "IDEMPOTENT_DUPLICATE"

def test_multiple_executor_instances(valid_action):
    # Scenario B: Same action_id on two executor instances
    executor1 = ActionExecutor()
    executor2 = ActionExecutor()
    
    # Exec 1
    success, reason = executor1.execute(valid_action)
    assert success
    
    # Exec 2
    success2, reason2 = executor2.execute(valid_action)
    assert not success2
    assert reason2 == "IDEMPOTENT_DUPLICATE"

def test_unknown_execution_state_recovery(executor, valid_action):
    # Scenario C: Executor crashed during execution (EXECUTING state)
    action_id = valid_action["action_id"]
    idem_key = f"action_exec:{action_id}"
    
    record = {
        "action_id": action_id,
        "executor_state": "EXECUTING",
        "execution_token": "token123"
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    # Retrying should hit RECONCILIATION_REQUIRED and block automatic execution
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "RECONCILIATION_REQUIRED"

def test_downstream_timeout(executor, valid_action):
    # Scenario K: Downstream timeout
    valid_action["mock_downstream_timeout"] = True
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "RECONCILIATION_REQUIRED"

    # Verify state in Redis is RECONCILIATION_REQUIRED
    action_id = valid_action["action_id"]
    idem_key = f"action_exec:{action_id}"
    record = json.loads(executor.redis.get(idem_key))
    assert record["executor_state"] == "RECONCILIATION_REQUIRED"

def test_crash_during_exec(executor, valid_action):
    # Scenario C part 2: Crash mid-execution
    valid_action["mock_crash_during_exec"] = True
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == "RECONCILIATION_REQUIRED"

    # Verify state in Redis is still EXECUTING because we crashed before writing FAILED
    action_id = valid_action["action_id"]
    idem_key = f"action_exec:{action_id}"
    record = json.loads(executor.redis.get(idem_key))
    assert record["executor_state"] == "EXECUTING"

def test_failed_execution_retry(executor, valid_action):
    # Scenario L: Failed execution followed by retry
    action_id = valid_action["action_id"]
    idem_key = f"action_exec:{action_id}"
    
    record = {
        "action_id": action_id,
        "executor_state": "FAILED",
        "execution_token": "old-token"
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    success, reason = executor.execute(valid_action)
    assert success
    assert reason == "EXECUTED"
    
def test_kill_switch(executor, valid_action):
    # Scenario K: Kill switch active
    from app.resilience.kill_switch import state as system_state
    system_state.activate_kill_switch("admin", "test")
    
    success, reason = executor.execute(valid_action)
    
    system_state.deactivate_kill_switch("admin", "test")
    
    assert not success
    assert reason == "KILL_SWITCH_ACTIVE"

def test_lease_renewal_success(executor, valid_action):
    # We can mock this by running execute but before it finishes we renew
    # Since execute is synchronous, we'll manually test renew_lease
    action_id = valid_action['action_id']
    idem_key = f'action_exec:{action_id}'
    
    # Pre-populate state
    now = datetime.now(timezone.utc)
    token = 'my-token'
    record = {
        'action_id': action_id,
        'executor_state': 'EXECUTING',
        'execution_token': token,
        'lease_started_at': now.isoformat(),
        'lease_expires_at': (now + timedelta(seconds=executor.initial_lease_seconds)).isoformat()
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    # Renew
    success = executor.renew_lease(action_id, token)
    assert success
    
    updated = json.loads(executor.redis.get(idem_key))
    assert datetime.fromisoformat(updated['lease_expires_at']) > datetime.fromisoformat(record['lease_expires_at'])

def test_lease_renewal_stale_executor(executor, valid_action):
    action_id = valid_action['action_id']
    idem_key = f'action_exec:{action_id}'
    now = datetime.now(timezone.utc)
    record = {
        'action_id': action_id,
        'executor_state': 'EXECUTING',
        'execution_token': 'real-token',
        'lease_started_at': now.isoformat(),
        'lease_expires_at': (now + timedelta(seconds=10)).isoformat()
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    success = executor.renew_lease(action_id, 'fake-token')
    assert not success

def test_lease_renewal_terminal_state(executor, valid_action):
    action_id = valid_action['action_id']
    idem_key = f'action_exec:{action_id}'
    now = datetime.now(timezone.utc)
    record = {
        'action_id': action_id,
        'executor_state': 'EXECUTED',
        'execution_token': 'my-token',
        'lease_started_at': now.isoformat(),
        'lease_expires_at': (now + timedelta(seconds=10)).isoformat()
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    success = executor.renew_lease(action_id, 'my-token')
    assert not success

def test_lease_renewal_max_lifetime(executor, valid_action):
    action_id = valid_action['action_id']
    idem_key = f'action_exec:{action_id}'
    now = datetime.now(timezone.utc)
    record = {
        'action_id': action_id,
        'executor_state': 'EXECUTING',
        'execution_token': 'my-token',
        # Started way back in the past
        'lease_started_at': (now - timedelta(seconds=100)).isoformat(),
        'lease_expires_at': (now + timedelta(seconds=10)).isoformat()
    }
    executor.redis.set(idem_key, json.dumps(record))
    
    success = executor.renew_lease(action_id, 'my-token')
    assert not success

def test_lease_expires_during_external_request(executor, valid_action):
    valid_action['mock_lose_lease'] = True
    success, reason = executor.execute(valid_action)
    assert not success
    assert reason == 'EXECUTED_BUT_LOST_LEASE'
    
    # State should be RECONCILIATION_REQUIRED
    idem_key = f"action_exec:{valid_action['action_id']}"
    record = json.loads(executor.redis.get(idem_key))
    assert record['executor_state'] == 'RECONCILIATION_REQUIRED'

