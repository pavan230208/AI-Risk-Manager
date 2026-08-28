import logging
from typing import List, Dict, Any
from app.risk.rule_engine import RiskSignal

logger = logging.getLogger(__name__)

class RiskScoreResult:
    def __init__(self, final_score: int, risk_level: str, signals: List[RiskSignal], ml_probability: float, requires_human_review: bool):
        self.final_score = final_score
        self.risk_level = risk_level  # SAFE, LOW, MEDIUM, HIGH, CRITICAL
        self.signals = signals
        self.ml_probability = ml_probability
        self.requires_human_review = requires_human_review

class RiskScorer:
    def __init__(self):
        # Weights for different severity levels
        self.severity_weights = {
            "CRITICAL": 100,
            "HIGH": 50,
            "MEDIUM": 20,
            "LOW": 5
        }
        
    def calculate_score(self, ml_result: Dict[str, Any], rule_signals: List[RiskSignal]) -> RiskScoreResult:
        """
        Merges ML probabilities and deterministic rule signals into a final score (0-100)
        and risk level.
        """
        base_score = 0
        
        # 1. Start with ML probability mapped to a 0-100 scale (weighted at 50% for standard anomalies)
        # If ML is missing/fallback, it contributes 0 to the base score, but rules take over.
        ml_prob = ml_result.get("probability", 0.0)
        import math
        if ml_result.get("status") == "success":
            try:
                if math.isnan(float(ml_prob)):
                    ml_prob = 0.0
                else:
                    base_score += int(ml_prob * 50)
            except (ValueError, TypeError):
                ml_prob = 0.0
            
        # 2. Add deterministic rule weights
        rule_score = sum(self.severity_weights.get(signal.severity, 0) for signal in rule_signals)
        
        # Combine and cap at 100
        final_score = min(100, base_score + rule_score)
        
        # 3. Determine Risk Level and Routing
        requires_human_review = False
        
        if final_score >= 85:
            risk_level = "CRITICAL"
            requires_human_review = True
        elif final_score >= 65:
            risk_level = "HIGH"
            requires_human_review = True
        elif final_score >= 35:
            risk_level = "MEDIUM"
            requires_human_review = True # Medium might go to human or automated challenge
        elif final_score >= 15:
            risk_level = "LOW"
        else:
            risk_level = "SAFE"
            
        # 4. Hard Deterministic Overrides
        # If any rule returned CRITICAL, immediately escalate to CRITICAL regardless of ML score
        has_critical = any(s.severity == "CRITICAL" for s in rule_signals)
        if has_critical:
            risk_level = "CRITICAL"
            final_score = max(final_score, 90)
            requires_human_review = True
            
        # If ML strongly indicates fraud but rules missed it (e.g. complex anomaly)
        if ml_result.get("is_risky", False) and final_score < 65:
            risk_level = "HIGH"
            final_score = max(final_score, 70)
            requires_human_review = True

        return RiskScoreResult(
            final_score=final_score,
            risk_level=risk_level,
            signals=rule_signals,
            ml_probability=ml_prob,
            requires_human_review=requires_human_review
        )
