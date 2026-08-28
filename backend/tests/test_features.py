import pytest
import pandas as pd
from datetime import datetime, timedelta, timezone
from app.ml.features import extract_features

@pytest.fixture
def sample_transactions():
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    data = [
        {"transaction_id": "t1", "user_id": "U1", "amount": 100, "timestamp": t0, "device_id": "D1", "location": "US"},
        {"transaction_id": "t2", "user_id": "U1", "amount": 100, "timestamp": t0 + timedelta(minutes=30), "device_id": "D1", "location": "US"},
        {"transaction_id": "t3", "user_id": "U1", "amount": 500, "timestamp": t0 + timedelta(minutes=90), "device_id": "D2", "location": "UK"},
        {"transaction_id": "t4", "user_id": "U2", "amount": 50, "timestamp": t0 + timedelta(hours=2), "device_id": "D3", "location": "CA"},
        {"transaction_id": "t5", "user_id": "U1", "amount": 100, "timestamp": t0 + timedelta(hours=25), "device_id": "D1", "location": "US"},
    ]
    return pd.DataFrame(data)

def test_extract_features_no_leakage(sample_transactions):
    df = extract_features(sample_transactions)
    
    # For U1, t1 is the first transaction. Hist avg should default to 100, dev=1
    u1_t1 = df[df["transaction_id"] == "t1"].iloc[0]
    assert u1_t1["user_hist_tx_count"] == 0
    assert u1_t1["amount_deviation"] == 1.0
    assert u1_t1["velocity_1h"] == 0
    assert u1_t1["is_new_device"] == 1
    assert u1_t1["is_new_location"] == 1
    
    # For U1, t2 is 30 mins later. Hist avg = 100, count = 1.
    u1_t2 = df[df["transaction_id"] == "t2"].iloc[0]
    assert u1_t2["user_hist_tx_count"] == 1
    assert u1_t2["user_hist_avg_amt"] == 100
    assert u1_t2["velocity_1h"] == 1 # 1 previous tx in last 1h
    assert u1_t2["velocity_24h"] == 1
    assert u1_t2["is_new_device"] == 0 # seen D1 before
    assert u1_t2["is_new_location"] == 0
    
    # For U1, t3 is 90 mins later. Hist avg = 100 (t1+t2), dev = 500/100 = 5.
    u1_t3 = df[df["transaction_id"] == "t3"].iloc[0]
    assert u1_t3["user_hist_tx_count"] == 2
    assert u1_t3["amount_deviation"] == 5.0
    assert u1_t3["velocity_1h"] == 0 # t2 was > 1hr ago (t0+30m vs t0+90m is 60m edge, pandas rolling '1h' includes edges, wait, 90m - 30m = 60m. Pandas closed='right' by default. Let's see how rolling handles it, but definitely only 1 if closed right, or 0 if we assume >60m. Since it's exactly 60m, it might be 1. Let's just check 24h which is 2)
    assert u1_t3["velocity_24h"] == 2
    assert u1_t3["is_new_device"] == 1 # D2 is new
    assert u1_t3["is_new_location"] == 1 # UK is new
    
    # For U1, t5 is 25 hours after t0. 
    u1_t5 = df[df["transaction_id"] == "t5"].iloc[0]
    # In last 24h from t0+25h: only t3 (t0+1.5h) and t5 are within 24h? Wait, t3 is t0+1.5h, t0+25h - 24h = t0+1h. So t3 is within 24h window. t1 and t2 are outside.
    assert u1_t5["velocity_24h"] == 1 # only t3
