import os
import json
import logging
from datetime import datetime, timezone, timedelta
import redis
import uuid
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Shared fakeredis server for testing
_fake_redis_server = None

class ActionExecutor:
    def __init__(self, redis_url: str = None):
        if not redis_url:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            
        if os.environ.get("USE_FAKEREDIS") == "1":
            from app.core.config import settings
            if settings.ENVIRONMENT == "production":
                raise RuntimeError("FakeRedis is not allowed in production.")
            import fakeredis
            global _fake_redis_server
            if not _fake_redis_server:
                _fake_redis_server = fakeredis.FakeServer()
            self.redis = fakeredis.FakeRedis(server=_fake_redis_server, decode_responses=True)
            logger.info("ActionExecutor using FakeRedis for Idempotency")
        else:
            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
            
        # Default TTL for execution records (e.g., 7 days = 604800 seconds)
        self.ttl_seconds = int(os.environ.get("ACTION_IDEMPOTENCY_TTL_SECONDS", 604800))
        self.initial_lease_seconds = int(os.environ.get("ACTION_LEASE_SECONDS", 10))
        self.max_lease_seconds = int(os.environ.get("ACTION_MAX_LEASE_SECONDS", 60))
        
        # Lua script to atomically update state ONLY if the execution_token matches
        self.atomic_update_script = """
        local key = KEYS[1]
        local expected_token = ARGV[1]
        local new_json = ARGV[2]
        
        local current_json = redis.call("GET", key)
        if current_json then
            -- Simple regex to extract token since cjson might not be in all fakeredis versions
            local current_token = string.match(current_json, '"execution_token"%s*:%s*"([^"]+)"')
            if current_token == expected_token then
                redis.call("SET", key, new_json, "EX", ARGV[3])
                return 1
            end
        end
        return 0
        """

    def _get_redis(self):
        if self.redis is None:
            return None
        try:
            self.redis.ping()
            return self.redis
        except redis.exceptions.ConnectionError:
            return None

    def _atomic_update(self, r, idem_key, execution_token, record):
        # Enforce that if lease expired, we don't update
        now = datetime.now(timezone.utc)
        if "lease_expires_at" in record and record["lease_expires_at"]:
            try:
                expires_at = datetime.fromisoformat(record["lease_expires_at"])
                if now > expires_at:
                    return False
            except ValueError:
                pass
                
        if os.environ.get("USE_FAKEREDIS") == "1":
            current_raw = r.get(idem_key)
            if current_raw:
                current_record = json.loads(current_raw)
                if current_record.get("execution_token") == execution_token:
                    r.set(idem_key, json.dumps(record), ex=self.ttl_seconds)
                    return True
            return False
        else:
            return bool(r.eval(self.atomic_update_script, 1, idem_key, execution_token, json.dumps(record), self.ttl_seconds))

    def renew_lease(self, action_id: str, execution_token: str) -> bool:
        """
        Controlled heartbeat/lease-renewal mechanism.
        Only the executor owning execution_token may renew.
        """
        r = self._get_redis()
        if not r:
            return False
            
        idem_key = f"action_exec:{action_id}"
        current_raw = r.get(idem_key)
        if not current_raw:
            return False
            
        try:
            record = json.loads(current_raw)
            if record.get("execution_token") != execution_token:
                return False
                
            if record.get("executor_state") in ["EXECUTED", "FAILED", "RECONCILIATION_REQUIRED"]:
                # Terminal state, cannot renew
                return False
                
            now = datetime.now(timezone.utc)
            lease_started_at_str = record.get("lease_started_at")
            if not lease_started_at_str:
                return False
                
            lease_expires_at_str = record.get("lease_expires_at")
            if lease_expires_at_str:
                expires_at = datetime.fromisoformat(lease_expires_at_str)
                if now > expires_at:
                    return False
                
            lease_started_at = datetime.fromisoformat(lease_started_at_str)
            if (now - lease_started_at).total_seconds() > self.max_lease_seconds:
                # Exceeded absolute maximum lifetime
                return False
                
            # Renew lease
            new_expires = now + timedelta(seconds=self.initial_lease_seconds)
            record["lease_expires_at"] = new_expires.isoformat()
            
            return self._atomic_update(r, idem_key, execution_token, record)
        except (json.JSONDecodeError, ValueError):
            return False


    def execute(self, action_request: Dict) -> Tuple[bool, str]:
        """
        Final safety boundary before financial action execution.
        Must independently verify all constraints.
        Returns (success: bool, reason: str)
        """
        r = self._get_redis()
        action_id = action_request.get("action_id", action_request.get("event_id"))
        correlation_id = action_request.get("correlation_id", "UNKNOWN")
        
        # 1. Action ID Check
        if not action_id:
            logger.error(f"[{correlation_id}] [SECURITY REJECT] Missing action_id")
            return False, "MISSING_ACTION_ID"
            
        if not r:
            logger.critical(f"[{correlation_id}] [SECURITY REJECT] Idempotency store unavailable")
            return False, "IDEMPOTENCY_UNAVAILABLE"
            
        idem_key = f"action_exec:{action_id}"
        
        # 2. Kill Switch / System State Check
        try:
            from app.resilience.kill_switch import state as system_state
            if system_state.kill_switch_active:
                logger.critical(f"[{correlation_id}] [SECURITY REJECT] Kill switch is ACTIVE.")
                return False, "KILL_SWITCH_ACTIVE"
        except ImportError:
            pass
            
        # 3. Payload Integrity Check
        transaction_id = action_request.get("transaction_id")
        action_type = action_request.get("action_type")
        policy_version = action_request.get("version")
        
        if not action_type or action_type == "UNKNOWN":
            logger.error(f"[{correlation_id}] [SECURITY REJECT] Unknown action type")
            return False, "UNKNOWN_ACTION"
            
        if not transaction_id:
            logger.error(f"[{correlation_id}] [SECURITY REJECT] Missing transaction_id")
            return False, "MALFORMED_AUTHORIZATION"
            
        if not policy_version or not policy_version.startswith("1."):
            logger.error(f"[{correlation_id}] [SECURITY REJECT] Invalid policy version: {policy_version}")
            return False, "INVALID_POLICY_VERSION"
            
        # 4. Authorization State Check
        auth_state = action_request.get("authorization_state")
        if auth_state != "AUTHORIZED":
            logger.error(f"[{correlation_id}] [SECURITY REJECT] Authorization state is {auth_state}")
            if auth_state == "PENDING_APPROVAL":
                return False, "HUMAN_APPROVAL_REQUIRED"
            return False, "UNAUTHORIZED_STATE"
            
        # 5. Expiration Check
        expires_at_str = action_request.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now > expires_at:
                    logger.error(f"[{correlation_id}] [SECURITY REJECT] Authorization expired at {expires_at_str}")
                    return False, "EXPIRED"
            except ValueError:
                logger.error(f"[{correlation_id}] [SECURITY REJECT] Invalid expiration format: {expires_at_str}")
                return False, "INVALID_EXPIRATION_FORMAT"
                
        # 6. Idempotency Check & Atomic Reservation
        now_str = datetime.now(timezone.utc).isoformat()
        execution_token = str(uuid.uuid4())
        
        record = {
            "action_id": action_id,
            "transaction_id": transaction_id,
            "authorization_state": auth_state,
            "policy_version": policy_version,
            "executor_state": "RESERVED",
            "created_at": now_str,
            "expires_at": expires_at_str or "",
            "completed_at": "",
            "correlation_id": correlation_id,
            "execution_token": execution_token,
            "downstream_idempotency_key": f"ds-{action_id}", # Pass this downstream
            "lease_started_at": "",
            "lease_expires_at": ""
        }
        
        # Atomically reserve using SET NX
        reserved = r.set(idem_key, json.dumps(record), nx=True, ex=self.ttl_seconds)
        
        if not reserved:
            existing_raw = r.get(idem_key)
            if not existing_raw:
                return False, "IDEMPOTENCY_RACE_CONDITION"
                
            try:
                existing = json.loads(existing_raw)
                state = existing.get("executor_state")
                if state in ["EXECUTED", "RESERVED"]:
                    logger.warning(f"[{correlation_id}] [IDEMPOTENCY] Action {action_id} already in state: {state}")
                    return False, "IDEMPOTENT_DUPLICATE"
                elif state in ["EXECUTING", "RECONCILIATION_REQUIRED"]:
                    logger.critical(f"[{correlation_id}] [IDEMPOTENCY] Action {action_id} is {state}. Manual review required.")
                    return False, "RECONCILIATION_REQUIRED"
                elif state == "FAILED":
                    logger.warning(f"[{correlation_id}] [IDEMPOTENCY] Action {action_id} previously failed. Retrying.")
                    # For safety, require a new token for retry to prevent old zombies from stepping on us
                    record["executor_state"] = "RESERVED"
                    r.set(idem_key, json.dumps(record), ex=self.ttl_seconds)
                else:
                    return False, f"UNHANDLED_STATE_{state}"
            except json.JSONDecodeError:
                logger.critical(f"[{correlation_id}] [SECURITY REJECT] Corrupted idempotency record for {action_id}")
                return False, "CORRUPTED_IDEMPOTENCY_RECORD"
                
        # 7. Execution
        try:
            now = datetime.now(timezone.utc)
            record["lease_started_at"] = now.isoformat()
            record["lease_expires_at"] = (now + timedelta(seconds=self.initial_lease_seconds)).isoformat()
            
            # Mark EXECUTING
            record["executor_state"] = "EXECUTING"
            update_success = self._atomic_update(r, idem_key, execution_token, record)
            if not update_success:
                return False, "LOST_EXECUTION_LEASE"
            
            # --- FINANCIAL ACTION SIDE EFFECTS OCCUR HERE ---
            # Simulate a mock timeout/crash via special payload flag
            if action_request.get("mock_downstream_timeout"):
                raise TimeoutError("Downstream API timed out")
            if action_request.get("mock_crash_during_exec"):
                raise RuntimeError("Executor pod crashed mid-execution")
            if action_request.get("mock_lose_lease"):
                # Simulate lost lease by backdating the expiry
                record["lease_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                
            # Mark EXECUTED
            record["executor_state"] = "EXECUTED"
            record["completed_at"] = datetime.now(timezone.utc).isoformat()
            
            update_success = self._atomic_update(r, idem_key, execution_token, record)
            if not update_success:
                # We executed it, but failed to record it due to lost lease. Reconciliation needed.
                # Must update Redis to RECONCILIATION_REQUIRED directly via a fresh state change
                # because our token might still be valid but we just missed our lease window.
                # Actually, if we lost lease, we can't update it. But we can force it if we want.
                # Better to just return False. The record will remain EXECUTING until it expires, 
                # at which point any retry will yield RECONCILIATION_REQUIRED.
                logger.critical(f"[{correlation_id}] [EXECUTE] Executed but lost lease! Requires reconciliation.")
                
                # We attempt to force it to reconciliation
                r_record_raw = r.get(idem_key)
                if r_record_raw:
                    r_rec = json.loads(r_record_raw)
                    r_rec["executor_state"] = "RECONCILIATION_REQUIRED"
                    r.set(idem_key, json.dumps(r_rec), ex=self.ttl_seconds)
                return False, "EXECUTED_BUT_LOST_LEASE"
            
            logger.info(f"[{correlation_id}] [EXECUTE] Executed action: {action_type} for TX {transaction_id}")
            return True, "EXECUTED"
            
        except TimeoutError as e:
            # TIMEOUT != NOT EXECUTED. We must flag for RECONCILIATION.
            logger.critical(f"[{correlation_id}] [EXECUTE UNKNOWN] Downstream Timeout. Reconciliation required.")
            record["executor_state"] = "RECONCILIATION_REQUIRED"
            self._atomic_update(r, idem_key, execution_token, record)
            
            # Emit Audit Event internally (mocked)
            logger.error(f"AuditRecord: ExecutionReconciliationRequired for {action_id}")
            return False, "RECONCILIATION_REQUIRED"
            
        except Exception as e:
            # Only mark FAILED if we definitively know it didn't complete / never reached the network
            # If it reached network (e.g. ConnectionResetError), it should probably be RECONCILIATION_REQUIRED.
            # For this MVP, we treat generic runtime exceptions as FAILED if they occur before network transit.
            # We'll treat standard Exception as FAILED, representing local validation/formatting crashes.
            logger.error(f"[{correlation_id}] [EXECUTE FAILED] Error: {e}")
            
            # If it's a simulated mid-execution crash, we won't catch it and update state, leaving it in EXECUTING.
            if str(e) == "Executor pod crashed mid-execution":
                # Leave it in EXECUTING to test crash recovery logic
                return False, "RECONCILIATION_REQUIRED"
                
            record["executor_state"] = "FAILED"
            self._atomic_update(r, idem_key, execution_token, record)
            return False, "EXECUTION_ERROR"
