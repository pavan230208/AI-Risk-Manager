import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import copy

logger = logging.getLogger(__name__)

class PolicyDefinition:
    def __init__(self, risk_level: str, permitted_action: str, requires_human_approval: bool, priority: int, reason: str, version: str):
        self.risk_level = risk_level
        self.permitted_action = permitted_action
        self.requires_human_approval = requires_human_approval
        self.priority = priority
        self.reason = reason
        self.version = version

class PolicyAction:
    def __init__(self, action_type: str, requires_human_approval: bool, reason: str, policy_id: str, version: str, input_risk_level: str, input_risk_score: int):
        self.action_type = action_type # e.g., 'BLOCK', 'ALLOW', 'CHALLENGE', 'REVIEW', 'FAIL_SAFE'
        self.requires_human_approval = requires_human_approval
        self.authorization_state = "PENDING_APPROVAL" if requires_human_approval else "AUTHORIZED"
        self.reason = reason
        self.policy_id = policy_id
        self.version = version
        self.input_risk_level = input_risk_level
        self.input_risk_score = input_risk_score
        self.timestamp = datetime.now(timezone.utc).isoformat()
        
    def to_dict(self):
        return {
            "action_type": self.action_type,
            "requires_human_approval": self.requires_human_approval,
            "authorization_state": self.authorization_state,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "version": self.version,
            "input_risk_level": self.input_risk_level,
            "input_risk_score": self.input_risk_score,
            "timestamp": self.timestamp
        }

class PolicyEngine:
    def __init__(self, config: Optional[Dict[str, PolicyDefinition]] = None):
        # Configurable policies with fail-safe defaults
        self.version = "1.0.0"
        
        if config is None:
            self.policies = {
                "SAFE": PolicyDefinition("SAFE", "ALLOW", False, 10, "Safe transaction profile. Autonomous execution permitted.", self.version),
                "LOW": PolicyDefinition("LOW", "ALLOW", False, 20, "Low risk transaction profile. Autonomous execution permitted.", self.version),
                "MEDIUM": PolicyDefinition("MEDIUM", "CHALLENGE", False, 30, "Medium risk profile; requesting automated step-up. Autonomous execution permitted.", self.version),
                "HIGH": PolicyDefinition("HIGH", "REVIEW", True, 40, "High risk profile; PENDING_APPROVAL. Requires human analyst review before execution.", self.version),
                "CRITICAL": PolicyDefinition("CRITICAL", "BLOCK", True, 50, "Critical risk profile; PENDING_APPROVAL. Requires human approval before executing block action.", self.version)
            }
        else:
            self.policies = config

    def evaluate_action(self, risk_score_result: Any) -> PolicyAction:
        """
        Takes the final risk score and determines the permissible action.
        Never modifies the risk score or ML probability.
        """
        # 1. Fail-Safe: Missing input
        if risk_score_result is None:
            logger.error("Fail-Safe Triggered: Missing RiskScoreResult")
            return self._fail_safe_action(reason="Missing RiskScoreResult")
            
        # 2. Immutability verification check 
        # Deep copy the risk_score_result internally to guarantee we don't accidentally mutate it
        try:
            immutable_copy = copy.deepcopy(risk_score_result)
        except Exception:
            logger.error("Fail-Safe Triggered: Could not verify immutability of input")
            return self._fail_safe_action(reason="Failed to verify immutability")
            
        risk_level = getattr(immutable_copy, 'risk_level', None)
        score = getattr(immutable_copy, 'final_score', None)
        
        # 3. Fail-Safe: Missing risk level or score
        if risk_level is None or score is None:
            logger.error("Fail-Safe Triggered: Missing risk level or score")
            return self._fail_safe_action(reason="Missing risk level or score")
            
        # 4. Fail-Safe: Unknown risk level
        if risk_level not in self.policies:
            logger.error(f"Fail-Safe Triggered: Unknown risk level '{risk_level}'")
            return self._fail_safe_action(reason=f"Unknown risk level: {risk_level}")
            
        policy = self.policies[risk_level]
        
        # 5. Fail-Safe: Invalid Policy
        if not isinstance(policy, PolicyDefinition) or not policy.permitted_action:
            logger.error(f"Fail-Safe Triggered: Invalid policy for risk level '{risk_level}'")
            return self._fail_safe_action(reason=f"Invalid policy for {risk_level}")
            
        # 6. Apply policy deterministically
        from app.resilience.kill_switch import state as system_state
        
        requires_human = policy.requires_human_approval
        if system_state.kill_switch_active:
            # Override autonomous execution if Kill Switch is active
            requires_human = True
            logger.warning(f"Kill Switch Active: Forcing human approval for {risk_level} transaction.")
            
        return PolicyAction(
            action_type=policy.permitted_action,
            requires_human_approval=requires_human,
            reason=policy.reason + (" (Kill Switch Active)" if system_state.kill_switch_active else ""),
            policy_id=f"POL-{risk_level}",
            version=policy.version,
            input_risk_level=risk_level,
            input_risk_score=score
        )
        
    def _fail_safe_action(self, reason: str) -> PolicyAction:
        return PolicyAction(
            action_type="FAIL_SAFE_BLOCK",
            requires_human_approval=True,
            reason=reason,
            policy_id="POL-FAILSAFE",
            version=self.version,
            input_risk_level="UNKNOWN",
            input_risk_score=-1
        )
