import pytest
from app.ml.inference import MLRiskEngine
from app.risk.scorer import RiskScorer
import pandas as pd
from unittest.mock import patch, MagicMock
from app.risk.rule_engine import RiskSignal

def test_ml_unavailable_fallback():
    engine = MLRiskEngine(model_path="invalid_path.joblib")
    assert engine.is_ready is False
    
    df = pd.DataFrame([{"amount": 100}])
    result = engine.predict(df)
    
    assert result["status"] == "fallback"
    assert "error" in result
    
    # Scorer should handle this gracefully
    scorer = RiskScorer()
    score_result = scorer.calculate_score(result, [])
    assert score_result.final_score == 0
    assert score_result.risk_level == "SAFE"

def test_ml_exception_during_predict():
    engine = MLRiskEngine()
    engine.is_ready = True
    engine.features = ["amount"]
    engine.scaler = MagicMock()
    engine.scaler.transform.side_effect = Exception("Scaler failed")
    
    df = pd.DataFrame([{"amount": 100}])
    result = engine.predict(df)
    
    assert result["status"] == "fallback"
    
def test_ml_nan_probability():
    # If ML returns NaN, the system should catch it or handle it gracefully.
    engine = MLRiskEngine()
    engine.is_ready = True
    engine.features = ["amount"]
    engine.scaler = MagicMock()
    engine.scaler.transform.return_value = [[100]]
    
    mock_model = MagicMock()
    import math
    mock_model.predict_proba.return_value = [[0.5, float('nan')]]
    engine.model = mock_model
    
    df = pd.DataFrame([{"amount": 100}])
    
    # Python float('nan') doesn't crash on standard > or < but propagates.
    # Our ML engine should handle NaN properly.
    result = engine.predict(df)
    
    # If it returns NaN, let's see how Scorer handles it
    scorer = RiskScorer()
    score_result = scorer.calculate_score(result, [])
    
    # We should ensure final_score is valid (not NaN)
    import math
    assert not math.isnan(score_result.final_score)
    # The vulnerability might be that it casts NaN to int, which raises ValueError.
    # Let's run this to see if it breaks.
