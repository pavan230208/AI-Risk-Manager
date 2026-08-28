import pytest
import pandas as pd
import numpy as np
from app.ml.features import extract_features

def test_missing_fields():
    df = pd.DataFrame([{"amount": 100}]) # Missing timestamp, user_id, device_id, location
    with pytest.raises(Exception):
        extract_features(df)

def test_malformed_timestamp():
    df = pd.DataFrame([{
        "user_id": "u1",
        "device_id": "d1",
        "location": "L1",
        "amount": 100.0,
        "timestamp": "not-a-date"
    }])
    # Depending on implementation, pd.to_datetime might raise an error
    with pytest.raises(Exception):
        extract_features(df)

def test_nan_amount():
    df = pd.DataFrame([{
        "user_id": "u1",
        "device_id": "d1",
        "location": "L1",
        "amount": float('nan'),
        "timestamp": "2026-08-25T12:00:00Z"
    }])
    # A NaN amount might propagate or crash. We should test if extract_features can handle or reject it safely.
    result = extract_features(df)
    # If it returns successfully, ensure no downstream crash occurs or it's handled safely.

def test_infinite_amount():
    df = pd.DataFrame([{
        "user_id": "u1",
        "device_id": "d1",
        "location": "L1",
        "amount": float('inf'),
        "timestamp": "2026-08-25T12:00:00Z"
    }])
    result = extract_features(df)
    # Ensure infinity is either handled or safely coerced.

def test_string_amount():
    df = pd.DataFrame([{
        "user_id": "u1",
        "device_id": "d1",
        "location": "L1",
        "amount": "100.0", # String instead of float
        "timestamp": "2026-08-25T12:00:00Z"
    }])
    # Might cause type errors in pandas math operations
    result = extract_features(df)

def test_null_values():
    df = pd.DataFrame([{
        "user_id": None,
        "device_id": None,
        "location": None,
        "amount": None,
        "timestamp": "2026-08-25T12:00:00Z"
    }])
    result = extract_features(df)
