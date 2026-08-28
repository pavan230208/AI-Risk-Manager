import asyncio
import httpx
import time
import statistics
import uuid
import uuid
from datetime import datetime, timezone
from collections import Counter

API_URL = "http://localhost:8000/api/v1/evaluate"
API_KEY = "production_api_key"

def generate_payload(tx_id=None):
    return {
        "transaction_id": tx_id or f"TXN-{uuid.uuid4()}",
        "user_id": "USR-100",
        "merchant_id": "MERCH-200",
        "amount": 100.0,
        "currency": "USD",
        "device_id": "DEV-300",
        "location": "US",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

async def fetch(client, tx_id=None):
    payload = generate_payload(tx_id)
    headers = {"X-API-Key": API_KEY}
    start = time.time()
    try:
        response = await client.post(API_URL, json=payload, headers=headers)
        elapsed = time.time() - start
        return response.status_code, elapsed, response.json()
    except Exception as e:
        elapsed = time.time() - start
        return 0, elapsed, str(e)

async def load_test(concurrency, duration, fixed_tx_id=None):
    results = []
    
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        start_time = time.time()
        
        async def worker():
            while time.time() - start_time < duration:
                res = await fetch(client, fixed_tx_id)
                results.append(res)
                
        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        
    return results

def print_stats(results, duration):
    total = len(results)
    statuses = Counter(r[0] for r in results)
    latencies = [r[1] for r in results]
    
    print(f"Total Requests: {total}")
    print(f"Throughput: {total / duration:.2f} req/s")
    for status, count in statuses.items():
        print(f"Status {status}: {count}")
        
    if latencies:
        print(f"Avg Latency: {statistics.mean(latencies):.4f}s")
        print(f"Median Latency: {statistics.median(latencies):.4f}s")
        print(f"P95 Latency: {statistics.quantiles(latencies, n=100)[94]:.4f}s")
        print(f"P99 Latency: {statistics.quantiles(latencies, n=100)[98]:.4f}s")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "low"
    
    duration = 10
    if mode == "low":
        concurrency = 5
        print("--- RUNNING LOW LOAD TEST ---")
    elif mode == "moderate":
        concurrency = 25
        print("--- RUNNING MODERATE LOAD TEST ---")
    elif mode == "high":
        concurrency = 50
        print("--- RUNNING HIGH LOAD TEST ---")
    elif mode == "idempotency":
        concurrency = 50
        print("--- RUNNING IDEMPOTENCY TEST ---")
        fixed_tx = str(uuid.uuid4())
        results = asyncio.run(load_test(concurrency, 5, fixed_tx))
        print_stats(results, 5)
        
        # Check execution statuses
        executions = [r[2].get("execution_status") for r in results if isinstance(r[2], dict)]
        exe_counts = Counter(executions)
        print("Executions:", exe_counts)
        sys.exit(0)
    else:
        print("Unknown mode")
        sys.exit(1)
        
    results = asyncio.run(load_test(concurrency, duration))
    print_stats(results, duration)
