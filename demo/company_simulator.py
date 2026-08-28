import urllib.request
import urllib.error
import json
import uuid
from datetime import datetime, timezone
import concurrent.futures

API_URL = "http://localhost:8000/api/v1/transactions/evaluate"
API_KEY = "production_api_key"

def get_base_tx():
    return {
        "transaction_id": f"SIM-{uuid.uuid4().hex[:8]}",
        "user_id": "customer_123",
        "merchant_id": "merchant_789",
        "amount": 50.0,
        "currency": "USD",
        "device_id": "dev_456",
        "location": "US",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def send_transaction(tx):
    req = urllib.request.Request(API_URL, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('X-API-Key', API_KEY)
    
    try:
        with urllib.request.urlopen(req, data=json.dumps(tx).encode('utf-8')) as response:
            res_body = json.loads(response.read().decode('utf-8'))
            print(f"[SUCCESS] TxID: {tx['transaction_id']} | Decision: {res_body.get('policy_action')} | Status: {res_body.get('execution_status')} | Score: {res_body.get('final_score')}")
            return res_body
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        print(f"[FAILED] HTTP {e.code}: {error_msg}")
        return None
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None

def main():
    print("==============================================")
    print(" COMPANY TRANSACTION SIMULATOR")
    print("==============================================\n")
    
    print("1. Sending SAFE transaction...")
    tx = get_base_tx()
    send_transaction(tx)
    
    print("\n2. Sending SUSPICIOUS transaction...")
    tx = get_base_tx()
    tx["amount"] = 3000
    tx["location"] = "RU"
    tx["device_id"] = "dev_new_unknown"
    send_transaction(tx)
    
    print("\n3. Sending CRITICAL transaction...")
    tx = get_base_tx()
    tx["amount"] = 80000
    tx["location"] = "KP"
    tx["device_id"] = "dev_hacked"
    send_transaction(tx)
    
    print("\n4. Sending 10 identical Duplicate transactions...")
    tx = get_base_tx()
    
    def fire():
        return send_transaction(tx)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(lambda _: fire(), range(10)))

if __name__ == "__main__":
    main()
