import pytest
from app.policy.engine import PolicyEngine, PolicyAction, PolicyDefinition
from app.risk.scorer import RiskScoreResult

@pytest.fixture
def engine():
    return PolicyEngine()

# 1. SAFE transaction
def test_1_safe_transaction(engine):
    score_result = RiskScoreResult(final_score=10, risk_level="SAFE", signals=[], ml_probability=0.1, requires_human_review=False)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "ALLOW"
    assert action.authorization_state == "AUTHORIZED"

# 2. LOW-risk transaction
def test_2_low_risk_transaction(engine):
    score_result = RiskScoreResult(final_score=25, risk_level="LOW", signals=[], ml_probability=0.2, requires_human_review=False)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "ALLOW"

# 3. MEDIUM-risk transaction
def test_3_medium_risk_transaction(engine):
    score_result = RiskScoreResult(final_score=45, risk_level="MEDIUM", signals=[], ml_probability=0.4, requires_human_review=True)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "CHALLENGE"

# 4. HIGH-risk transaction
def test_4_high_risk_transaction(engine):
    score_result = RiskScoreResult(final_score=75, risk_level="HIGH", signals=[], ml_probability=0.7, requires_human_review=True)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "REVIEW"

# 5. CRITICAL-risk transaction
def test_5_critical_risk_transaction(engine):
    score_result = RiskScoreResult(final_score=95, risk_level="CRITICAL", signals=[], ml_probability=0.95, requires_human_review=True)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "BLOCK"

# 6. Mandatory human approval
def test_6_mandatory_human_approval(engine):
    score_result = RiskScoreResult(final_score=95, risk_level="CRITICAL", signals=[], ml_probability=0.95, requires_human_review=True)
    action = engine.evaluate_action(score_result)
    assert action.requires_human_approval is True
    assert action.authorization_state == "PENDING_APPROVAL"

# 7. Policy not found (Same as unknown risk level in this implementation, but explicit)
def test_7_policy_not_found():
    custom_engine = PolicyEngine(config={"ONLY_SAFE": PolicyDefinition("ONLY_SAFE", "ALLOW", False, 10, "Safe", "1.0")})
    score_result = RiskScoreResult(final_score=50, risk_level="UNKNOWN_LEVEL", signals=[], ml_probability=0.5, requires_human_review=False)
    action = custom_engine.evaluate_action(score_result)
    assert action.action_type == "FAIL_SAFE_BLOCK"

# 8. Invalid policy
def test_8_invalid_policy():
    custom_config = {"SAFE": "This is a string, not a PolicyDefinition"}
    custom_engine = PolicyEngine(config=custom_config)
    score_result = RiskScoreResult(final_score=10, risk_level="SAFE", signals=[], ml_probability=0.1, requires_human_review=False)
    action = custom_engine.evaluate_action(score_result)
    assert action.action_type == "FAIL_SAFE_BLOCK"

# 9. Unknown risk level
def test_9_unknown_risk_level(engine):
    score_result = RiskScoreResult(final_score=50, risk_level="ALIEN", signals=[], ml_probability=0.5, requires_human_review=False)
    action = engine.evaluate_action(score_result)
    assert action.action_type == "FAIL_SAFE_BLOCK"
    assert "Unknown risk level" in action.reason

# 10. Missing RiskScoreResult
def test_10_missing_risk_score_result(engine):
    action = engine.evaluate_action(None)
    assert action.action_type == "FAIL_SAFE_BLOCK"
    
# 11. Unauthorized action (A policy explicitly denying an action by having empty string for action)
def test_11_unauthorized_action():
    custom_engine = PolicyEngine(config={"SAFE": PolicyDefinition("SAFE", "", False, 10, "Empty action", "1.0")})
    score_result = RiskScoreResult(final_score=10, risk_level="SAFE", signals=[], ml_probability=0.1, requires_human_review=False)
    action = custom_engine.evaluate_action(score_result)
    assert action.action_type == "FAIL_SAFE_BLOCK"

# 12. Policy immutability
def test_12_policy_immutability(engine):
    score_result = RiskScoreResult(final_score=10, risk_level="SAFE", signals=[], ml_probability=0.1, requires_human_review=False)
    action = engine.evaluate_action(score_result)
    assert score_result.final_score == 10
    assert score_result.risk_level == "SAFE"

# 13. Deterministic repeated decisions
def test_13_deterministic_repeated_decisions(engine):
    score_result = RiskScoreResult(final_score=75, risk_level="HIGH", signals=[], ml_probability=0.7, requires_human_review=True)
    action1 = engine.evaluate_action(score_result)
    action2 = engine.evaluate_action(score_result)
    assert action1.to_dict()["action_type"] == action2.to_dict()["action_type"]

# 14. Policy version handling
def test_14_policy_version_handling():
    custom_config = {"SAFE": PolicyDefinition("SAFE", "ALLOW", False, 10, "Safe", "2.5.0")}
    custom_engine = PolicyEngine(config=custom_config)
    score_result = RiskScoreResult(final_score=10, risk_level="SAFE", signals=[], ml_probability=0.1, requires_human_review=False)
    action = custom_engine.evaluate_action(score_result)
    assert action.version == "2.5.0"

# 15. Fail-safe behavior (Explicit check of authorization state on fail-safe)
def test_15_fail_safe_behavior(engine):
    action = engine.evaluate_action(None)
    assert action.action_type == "FAIL_SAFE_BLOCK"
    assert action.requires_human_approval is True
    assert action.authorization_state == "PENDING_APPROVAL"
