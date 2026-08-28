import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class RiskSignal:
    def __init__(self, rule_name: str, signal_type: str, description: str, severity: str):
        self.rule_name = rule_name
        self.signal_type = signal_type # e.g., 'VELOCITY', 'AMOUNT', 'DEVICE'
        self.description = description
        self.severity = severity # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'

class DeterministicRuleEngine:
    def __init__(self):
        self.rules = [
            self.rule_velocity_spike,
            self.rule_extreme_amount,
            self.rule_new_device_high_amount
        ]

    def evaluate(self, transaction_data: Dict, features: Dict) -> List[RiskSignal]:
        signals = []
        for rule in self.rules:
            try:
                signal = rule(transaction_data, features)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Rule {rule.__name__} failed: {e}")
                # Fail-safe: continue evaluating other rules
        return signals

    def rule_velocity_spike(self, tx: Dict, features: Dict):
        vel_1h = features.get('velocity_1h', 0)
        if vel_1h >= 10:
            return RiskSignal(
                rule_name="rule_velocity_spike",
                signal_type="VELOCITY",
                description=f"High velocity detected: {vel_1h} transactions in 1 hour.",
                severity="HIGH"
            )
        return None

    def rule_extreme_amount(self, tx: Dict, features: Dict):
        amount = tx.get('amount', 0.0)
        # Using a more robust threshold or historical deviation
        deviation = features.get('amount_deviation', 1.0)
        if amount > 5000 or deviation > 5.0:
            return RiskSignal(
                rule_name="rule_extreme_amount",
                signal_type="AMOUNT",
                description=f"Extreme transaction amount: ${amount} or deviation {deviation:.2f}x",
                severity="CRITICAL"
            )
        return None

    def rule_new_device_high_amount(self, tx: Dict, features: Dict):
        is_new_device = features.get('is_new_device', 0)
        amount = tx.get('amount', 0.0)
        
        if is_new_device == 1 and amount > 500:
            return RiskSignal(
                rule_name="rule_new_device_high_amount",
                signal_type="DEVICE",
                description="Transaction over $500 from a previously unseen device.",
                severity="HIGH"
            )
        return None
