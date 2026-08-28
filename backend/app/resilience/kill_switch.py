import logging

logger = logging.getLogger(__name__)

class SystemModes:
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    AUTONOMOUS_ACTIONS_DISABLED = "AUTONOMOUS_ACTIONS_DISABLED"

class SystemState:
    def __init__(self):
        self.mode = SystemModes.NORMAL
        self.kill_switch_active = False
        
    def activate_kill_switch(self, user: str, reason: str):
        logger.critical(f"[KILL SWITCH] ACTIVATED by {user}. Reason: {reason}")
        self.kill_switch_active = True
        self.mode = SystemModes.AUTONOMOUS_ACTIONS_DISABLED
        
    def deactivate_kill_switch(self, user: str, reason: str):
        logger.warning(f"[KILL SWITCH] DEACTIVATED by {user}. Reason: {reason}")
        self.kill_switch_active = False
        self.mode = SystemModes.NORMAL
        
    def set_degraded_mode(self):
        if not self.kill_switch_active:
            self.mode = SystemModes.DEGRADED
            logger.warning("[SYSTEM STATE] Entered DEGRADED mode.")
            
    def recover_normal_mode(self):
        if not self.kill_switch_active:
            self.mode = SystemModes.NORMAL
            logger.info("[SYSTEM STATE] Recovered to NORMAL mode.")

# Global state for demonstration
state = SystemState()
