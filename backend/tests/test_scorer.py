import pytest
from app.risk.scorer import RiskScorer
from app.risk.rule_engine import RiskSignal

@pytest.fixture
def scorer():
    return RiskScorer()

def test_safe_transaction(scorer):
    ml_result = {"status": "success", "probability": 0.05, "is_risky": False}
    signals = []
    
    result = scorer.calculate_score(ml_result, signals)
    assert result.final_score == 2  # 0.05 * 50
    assert result.risk_level == "SAFE"
    assert result.requires_human_review is False

def test_ml_high_risk_override(scorer):
    # ML says risky, but rules don't catch it
    ml_result = {"status": "success", "probability": 0.85, "is_risky": True}
    signals = []
    
    result = scorer.calculate_score(ml_result, signals)
    assert result.final_score == 70  # Override to 70
    assert result.risk_level == "HIGH"
    assert result.requires_human_review is True

def test_deterministic_critical_override(scorer):
    # ML says very safe, but rule says CRITICAL
    ml_result = {"status": "success", "probability": 0.01, "is_risky": False}
    signals = [RiskSignal("rule_extreme_amount", "AMOUNT", "Extreme", "CRITICAL")]
    
    result = scorer.calculate_score(ml_result, signals)
    assert result.final_score >= 90
    assert result.risk_level == "CRITICAL"
    assert result.requires_human_review is True

def test_ml_fallback_rules_handle_it(scorer):
    # ML model is down/fallback
    ml_result = {"status": "fallback", "error": "Model offline"}
    signals = [RiskSignal("rule_velocity_spike", "VELOCITY", "Spike", "HIGH")]
    
    result = scorer.calculate_score(ml_result, signals)
    assert result.final_score == 50 # Base 0 + 50 for HIGH rule
    assert result.risk_level == "MEDIUM" 
    assert result.requires_human_review is True
