import pytest
from app.risk.rule_engine import DeterministicRuleEngine

@pytest.fixture
def engine():
    return DeterministicRuleEngine()

def test_no_signals(engine):
    tx = {"amount": 50.0}
    features = {"velocity_1h": 1, "is_new_device": 0}
    
    signals = engine.evaluate(tx, features)
    assert len(signals) == 0

def test_velocity_spike(engine):
    tx = {"amount": 50.0}
    features = {"velocity_1h": 11, "is_new_device": 0}
    
    signals = engine.evaluate(tx, features)
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_velocity_spike"
    assert signals[0].severity == "HIGH"

def test_extreme_amount(engine):
    tx = {"amount": 15000.0}
    features = {"velocity_1h": 1, "is_new_device": 0}
    
    signals = engine.evaluate(tx, features)
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_extreme_amount"
    assert signals[0].severity == "CRITICAL"

def test_multiple_signals(engine):
    tx = {"amount": 15000.0}
    features = {"velocity_1h": 10, "is_new_device": 1}
    
    signals = engine.evaluate(tx, features)
    assert len(signals) == 3
    
    rule_names = [s.rule_name for s in signals]
    assert "rule_velocity_spike" in rule_names
    assert "rule_extreme_amount" in rule_names
    assert "rule_new_device_high_amount" in rule_names
