import pytest
from app.risk.rule_engine import DeterministicRuleEngine

@pytest.fixture
def rule_engine():
    return DeterministicRuleEngine()

def test_rule_velocity_spike(rule_engine):
    tx = {"amount": 50.0}
    features = {"velocity_1h": 12}
    signals = rule_engine.evaluate(tx, features)
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_velocity_spike"
    assert signals[0].severity == "HIGH"

def test_rule_extreme_amount_absolute(rule_engine):
    tx = {"amount": 6000.0}
    features = {"amount_deviation": 1.0}
    signals = rule_engine.evaluate(tx, features)
    assert any(s.rule_name == "rule_extreme_amount" for s in signals)
    assert any(s.severity == "CRITICAL" for s in signals)

def test_rule_extreme_amount_deviation(rule_engine):
    tx = {"amount": 200.0}
    features = {"amount_deviation": 6.5}
    signals = rule_engine.evaluate(tx, features)
    assert any(s.rule_name == "rule_extreme_amount" for s in signals)

def test_rule_new_device_high_amount(rule_engine):
    tx = {"amount": 600.0}
    features = {"is_new_device": 1}
    signals = rule_engine.evaluate(tx, features)
    assert any(s.rule_name == "rule_new_device_high_amount" for s in signals)

def test_multiple_simultaneous_anomalies(rule_engine):
    tx = {"amount": 6000.0}
    features = {"is_new_device": 1, "velocity_1h": 15, "amount_deviation": 10.0}
    signals = rule_engine.evaluate(tx, features)
    rule_names = [s.rule_name for s in signals]
    assert "rule_velocity_spike" in rule_names
    assert "rule_extreme_amount" in rule_names
    assert "rule_new_device_high_amount" in rule_names
    assert len(signals) == 3
