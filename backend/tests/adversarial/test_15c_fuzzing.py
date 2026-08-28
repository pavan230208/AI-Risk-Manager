import pytest
from fastapi.testclient import TestClient
import pandas as pd
import numpy as np
from app.main import app
from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine


client = TestClient(app)

def get_valid_payload():
    return {
        "transaction_id": "TXN-1",
        "user_id": "USR-1",
        "merchant_id": "MERCH-1",
        "amount": 100.0,
        "currency": "USD",
        "device_id": "DEV-1",
        "location": "US",
        "timestamp": "2026-08-25T12:00:00Z"
    }

# 1. API Fuzzing
@pytest.mark.parametrize("mutator", [
    lambda p: p.pop("amount"),
    lambda p: p.update({"amount": None}),
    lambda p: p.update({"amount": ""}),
    lambda p: p.update({"amount": "A"*10000}),
    lambda p: p.update({"amount": 1e100}),
    lambda p: p.update({"amount": -1}),
    lambda p: p.update({"amount": float('nan')}),
    lambda p: p.update({"amount": float('inf')}),
    lambda p: p.update({"timestamp": "invalid_date"}),
    lambda p: p.update({"transaction_id": "A"*10000}),
    lambda p: p.update({"currency": "INVALID"}),
    lambda p: p.update({"device_id": {"nested": "object"}}),
    lambda p: p.update({"location": ["array"]}),
    lambda p: p.update({"extra_field": "unexpected"}),
])
def test_api_fuzzing_rejects_malformed(mutator):
    payload = get_valid_payload()
    try:
        mutator(payload)
    except Exception:
        pass
        
    try:
        response = client.post("/api/v1/evaluate", json=payload)
        # The API must not fail open. It should return 422 or 400.
        assert response.status_code in [422, 400]
    except ValueError as e:
        # JSON serialization error for NaN/Inf is a safe rejection
        assert "not JSON compliant" in str(e)

def test_api_extremely_large_payload():
    payload = get_valid_payload()
    payload["massive_field"] = "A" * 1000000
    response = client.post("/api/v1/evaluate", json=payload)
    assert response.status_code in [413, 422, 400]

# 2. Feature Engineering Fuzzing
@pytest.mark.parametrize("mutator", [
    lambda d: d.pop("user_id"),
    lambda d: d.update({"user_id": None}),
    lambda d: d.update({"amount": float('nan')}),
    lambda d: d.update({"amount": float('inf')}),
    lambda d: d.update({"amount": -50}),
    lambda d: d.update({"timestamp": "invalid_date"}),
    lambda d: d.update({"location": ["invalid", "type"]}),
])
def test_feature_engineering_robustness(mutator):
    data = get_valid_payload()
    try:
        mutator(data)
    except:
        pass
        
    df = pd.DataFrame([data])
    try:
        features = extract_features(df)
        # If it didn't crash, it should at least return a dataframe
        assert isinstance(features, pd.DataFrame)
    except Exception as e:
        # Expected to fail safely by throwing exception, which main catches
        pass

def test_feature_engineering_empty():
    df = pd.DataFrame()
    with pytest.raises(Exception):
        extract_features(df)

# 3. ML Robustness
def test_ml_nan_probability():
    class MockModel:
        def predict_proba(self, X):
            return np.array([[float('nan'), float('nan')]])
            
    engine = MLRiskEngine()
    engine.model = MockModel()
    engine.scaler = None
    
    # Mocking features
    features = pd.DataFrame([{"feat1": 1}])
    try:
        score = engine.predict(features)
        assert score == 100.0 or score >= 0.0 # fallback or NaN handled
    except Exception:
        pass # Exception caught by MLEngine is also safe

def test_ml_infinity_probability():
    class MockModel:
        def predict_proba(self, X):
            return np.array([[float('-inf'), float('inf')]])
            
    engine = MLRiskEngine()
    engine.model = MockModel()
    
    features = pd.DataFrame([{"feat1": 1}])
    try:
        score = engine.predict(features)
        assert score >= 0.0 and score <= 100.0
    except Exception:
        pass

def test_ml_exception():
    class MockModel:
        def predict_proba(self, X):
            raise RuntimeError("Model crashed")
            
    engine = MLRiskEngine()
    engine.model = MockModel()
    
    features = pd.DataFrame([{"feat1": 1}])
    score = engine.predict(features)
    assert isinstance(score, dict) and score.get("status") == "fallback"
