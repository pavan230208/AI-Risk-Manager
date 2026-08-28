import json
import logging
from app.actions.executor import ActionExecutor

logger = logging.getLogger(__name__)

class AutomationState:
    def __init__(self):
        self._executor = ActionExecutor()
        self.state_key = "system:automated_protection_enabled"

    @property
    def is_enabled(self) -> bool:
        redis_conn = self._executor._get_redis()
        if not redis_conn:
            return False
        try:
            val = redis_conn.get(self.state_key)
            if val is None:
                return False
            return json.loads(val)
        except Exception as e:
            logger.error(f"Failed to read automated_protection_enabled: {e}")
            return False

    def enable(self):
        redis_conn = self._executor._get_redis()
        if redis_conn:
            redis_conn.set(self.state_key, json.dumps(True))

    def disable(self):
        redis_conn = self._executor._get_redis()
        if redis_conn:
            redis_conn.set(self.state_key, json.dumps(False))

automation_state = AutomationState()
