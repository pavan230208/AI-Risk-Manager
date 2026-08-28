import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uuid
import os

def generate_synthetic_data(num_users=1000, num_merchants=50, num_transactions=10000, random_state=42):
    np.random.seed(random_state)
    
    users = [f"U{i}" for i in range(1, num_users + 1)]
    merchants = [f"M{i}" for i in range(1, num_merchants + 1)]
    locations = ["US", "UK", "CA", "IN", "AU", "DE", "FR"]
    
    # Base legitimate transactions
    data = []
    
    # User profiles
    user_profiles = {}
    for user in users:
        user_profiles[user] = {
            "avg_amount": np.random.lognormal(mean=3, sigma=1), # typical amount
            "primary_location": np.random.choice(locations, p=[0.5, 0.1, 0.1, 0.1, 0.05, 0.05, 0.1]),
            "primary_device": f"D_{np.random.randint(1000, 9999)}"
        }
        
    start_date = datetime.utcnow() - timedelta(days=30)
    
    # Generate sequential transactions
    for _ in range(num_transactions):
        user = np.random.choice(users)
        profile = user_profiles[user]
        
        # Legitimate parameters
        amount = max(1.0, np.random.normal(loc=profile["avg_amount"], scale=profile["avg_amount"] * 0.2))
        location = profile["primary_location"] if np.random.random() > 0.1 else np.random.choice(locations)
        device = profile["primary_device"] if np.random.random() > 0.05 else f"D_{np.random.randint(1000, 9999)}"
        timestamp = start_date + timedelta(seconds=np.random.randint(0, 30 * 24 * 3600))
        merchant = np.random.choice(merchants)
        
        data.append({
            "transaction_id": str(uuid.uuid4()),
            "user_id": user,
            "merchant_id": merchant,
            "amount": amount,
            "currency": "USD",
            "payment_method": "CREDIT_CARD",
            "device_id": device,
            "location": location,
            "timestamp": timestamp,
            "is_fraud": 0,
            "fraud_type": "none"
        })
        
    df = pd.DataFrame(data)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # Inject anomalies (approx 3% fraud)
    num_fraud = int(num_transactions * 0.03)
    fraud_indices = np.random.choice(df.index, size=num_fraud, replace=False)
    
    for idx in fraud_indices:
        fraud_type = np.random.choice(["amount", "velocity", "device_geo"])
        user = df.at[idx, "user_id"]
        profile = user_profiles[user]
        
        df.at[idx, "is_fraud"] = 1
        df.at[idx, "fraud_type"] = fraud_type
        
        if fraud_type == "amount":
            # 5x to 15x normal amount
            df.at[idx, "amount"] = profile["avg_amount"] * np.random.uniform(5, 15)
        elif fraud_type == "velocity":
            # Make the timestamp very close to the previous transaction of this user (if exists)
            user_txs = df[df["user_id"] == user]
            if len(user_txs) > 1:
                prev_time = user_txs["timestamp"].min()
                df.at[idx, "timestamp"] = prev_time + timedelta(seconds=np.random.randint(1, 60))
        elif fraud_type == "device_geo":
            # Change device and location far from primary
            df.at[idx, "device_id"] = f"D_HACKER_{np.random.randint(10, 99)}"
            df.at[idx, "location"] = "RU" if profile["primary_location"] != "RU" else "CN"
            df.at[idx, "amount"] = profile["avg_amount"] * np.random.uniform(2, 5) # Elevated amount too
            
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # Train/Val/Test Split (70/15/15) based on time
    n_total = len(df)
    train_end = int(n_total * 0.70)
    val_end = int(n_total * 0.85)
    
    df["split"] = "train"
    df.loc[train_end:val_end, "split"] = "val"
    df.loc[val_end:, "split"] = "test"
    
    return df

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    os.makedirs(output_dir, exist_ok=True)
    
    print("Generating synthetic transaction data...")
    df = generate_synthetic_data(num_users=2000, num_merchants=100, num_transactions=25000)
    
    csv_path = os.path.join(output_dir, "synthetic_transactions.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"Dataset generated with {len(df)} records.")
    print(df["split"].value_counts())
    print("\nFraud Distribution:")
    print(df["is_fraud"].value_counts(normalize=True) * 100)
    print("\nFraud Types:")
    print(df[df["is_fraud"] == 1]["fraud_type"].value_counts())
    print(f"\nSaved to {csv_path}")
