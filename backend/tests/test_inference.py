import pytest
import pandas as pd
from datetime import datetime, timezone
import os

from app.ml.inference import MLRiskEngine

def test_inference_fallback():
    # Force engine to load a non-existent model
    engine = MLRiskEngine(model_path="/fake/path/model.joblib")
    
    # Try prediction
    result = engine.predict(pd.DataFrame())
    
    assert result["status"] == "fallback"
    assert "error" in result

from app.core.config import settings

def test_inference_correctness():
    # Use the real model path centralized from settings
    model_path = os.path.join(settings.DATA_DIR, "models", "risk_model_v1.joblib")
    
    # Only run if model exists (e.g. training script was run)
    if not os.path.exists(model_path):
        pytest.skip("Model artifact not found. Run train_model.py first.")
        
    engine = MLRiskEngine(model_path=model_path)
    assert engine.is_ready is True
    
    # Create a synthetic transaction with pre-extracted features
    # features: ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']
    data = {
        'amount': [100.0],
        'user_hist_avg_amt': [100.0],
        'amount_deviation': [1.0],
        'velocity_1h': [0],
        'velocity_24h': [0],
        'is_new_device': [0],
        'is_new_location': [0]
    }
    df_features = pd.DataFrame(data)
    
    result = engine.predict(df_features)
    
    assert result["status"] == "success"
    assert "probability" in result
    assert "is_risky" in result
    assert result["probability"] >= 0.0 and result["probability"] <= 1.0
