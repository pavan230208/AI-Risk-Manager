import os
import sys
import pandas as pd
from datetime import datetime
import json
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__))))

from app.ml.features import extract_features
from app.ml.inference import MLRiskEngine
from app.models.core import User
from app.models.transaction import Transaction
from app.db.database import SessionLocal, engine
from app.models.base import Base

def run_demo():
    print("============================================================")
    print("1. CURRENT COMPLETED PHASES: Phase 5 (ML Risk Model)")
    print("============================================================\n")

    print("============================================================")
    print("4. ML/RISK PIPELINE DEMONSTRATION")
    print("============================================================")
    
    # Load 5 sample transactions from the generated synthetic data
    from app.core.config import settings
    csv_path = os.path.join(settings.DATA_DIR, "synthetic_transactions.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path).head(5)
    
    print("--- Input Transactions (Raw) ---")
    print(df[['transaction_id', 'user_id', 'amount', 'timestamp']].to_string(index=False))
    
    print("\n--- Feature Extraction ---")
    df_features = extract_features(df)
    feature_cols = ['amount', 'user_hist_avg_amt', 'amount_deviation', 'velocity_1h', 'velocity_24h', 'is_new_device', 'is_new_location']
    print(df_features[['transaction_id'] + feature_cols].to_string(index=False))
    
    print("\n--- ML Prediction & Risk Classification ---")
    ml_engine = MLRiskEngine()
    if not ml_engine.is_ready:
        print("Model not ready. Please ensure model training was successful.")
    else:
        for idx, row in df_features.iterrows():
            # Pass a single-row dataframe for prediction to maintain column structures
            single_tx_df = pd.DataFrame([row])
            result = ml_engine.predict(single_tx_df)
            print(f"Transaction ID: {row['transaction_id']}")
            print(f"  Probability: {result.get('probability', 'N/A'):.4f}")
            print(f"  Threshold:   {result.get('threshold', 'N/A')}")
            print(f"  Is Risky:    {result.get('is_risky', 'N/A')}")
            print(f"  Status:      {result.get('status')}\n")

    print("============================================================")
    print("6. API OUTPUT DEMONSTRATION")
    print("============================================================")
    print("FastAPI endpoints implemented so far: GET /health, GET /api/v1/status")
    print("API is currently skeletal. Fully functional business routes: NOT IMPLEMENTED YET")

    print("\n============================================================")
    print("7. DATABASE OUTPUT DEMONSTRATION")
    print("============================================================")
    
    # Setup in-memory DB for demo purposes
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Insert a user
    demo_user = User(email="demo@riskmanager.ai", hashed_password="hashed", role="ADMIN")
    db.add(demo_user)
    db.commit()
    db.refresh(demo_user)
    
    print(f"Successfully inserted User: ID={demo_user.id}, Email={demo_user.email}, Role={demo_user.role}")
    
    # Insert a transaction
    demo_tx = Transaction(
        id="TXN-DEMO-999", user_id=str(demo_user.id), merchant_id="M_DEMO",
        amount=1250.00, currency="USD", payment_method="CREDIT_CARD", status="PENDING"
    )
    db.add(demo_tx)
    db.commit()
    
    # Fetch it back
    fetched_tx = db.query(Transaction).filter(Transaction.id == "TXN-DEMO-999").first()
    print(f"Successfully retrieved Transaction: ID={fetched_tx.id}, Amount={fetched_tx.amount}, Status={fetched_tx.status}")
    
    db.close()

    print("\n============================================================")
    print("9. FRONTEND DEMONSTRATION")
    print("============================================================")
    print("Next.js scaffold has been created in /frontend.")
    print("Usable UI functionality: NOT IMPLEMENTED YET")

if __name__ == "__main__":
    run_demo()
