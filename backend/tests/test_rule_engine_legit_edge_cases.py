import pytest
from app.risk.rule_engine import DeterministicRuleEngine

@pytest.fixture
def rule_engine():
    return DeterministicRuleEngine()

def test_legitimate_unusually_large_transaction(rule_engine):
    # A perfectly legitimate user suddenly making a massive transaction
    tx = {"amount": 8000.0}
    features = {"amount_deviation": 6.0}
    signals = rule_engine.evaluate(tx, features)
    
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_extreme_amount"
    assert signals[0].severity == "CRITICAL"
    # It identifies a RISK SIGNAL, not confirmed fraud (score is calculated later)

def test_legitimate_new_device(rule_engine):
    # A legitimate user using a new device but with normal amount
    tx = {"amount": 100.0}
    features = {"is_new_device": 1, "amount_deviation": 1.0}
    signals = rule_engine.evaluate(tx, features)
    
    # Doesn't breach new_device_high_amount (amount > 500)
    assert len(signals) == 0

def test_legitimate_new_device_large_transaction(rule_engine):
    # A legitimate user using a new device to buy a TV
    tx = {"amount": 800.0}
    features = {"is_new_device": 1, "amount_deviation": 2.0}
    signals = rule_engine.evaluate(tx, features)
    
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_new_device_high_amount"
    assert signals[0].severity == "HIGH"
    # Identifies a HIGH risk signal, which will prompt a step-up challenge, not ban

def test_legitimate_high_velocity(rule_engine):
    # A legitimate user buying many small items rapidly (e.g. at an arcade)
    tx = {"amount": 10.0}
    features = {"velocity_1h": 15, "amount_deviation": 1.0}
    signals = rule_engine.evaluate(tx, features)
    
    assert len(signals) == 1
    assert signals[0].rule_name == "rule_velocity_spike"
    assert signals[0].severity == "HIGH"
    # Identifies a HIGH risk signal.
