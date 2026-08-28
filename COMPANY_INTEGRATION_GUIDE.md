# COMPANY INTEGRATION GUIDE

Integrating the Autonomous AI Risk Manager into your existing business pipeline is straightforward and secure.

## 1. Prerequisites
- Provide an integration request to the Risk Manager administrators to generate a secure `X-API-Key`.
- Ensure the Risk Manager administrators have enabled "Automated Protection" via the Dashboard.

## 2. API Endpoint
```
POST /api/v1/transactions/evaluate
```

## 3. Authentication
Attach your provided API key to the HTTP header.
```
X-API-Key: <your_production_api_key>
```

## 4. Request Payload
Send a JSON payload conforming strictly to the transaction schema.
```json
{
  "transaction_id": "txn_8008135",
  "user_id": "usr_99",
  "merchant_id": "merch_102",
  "amount": 25000.0,
  "currency": "USD",
  "device_id": "dev_hacked",
  "location": "US",
  "timestamp": "2026-08-27T12:00:00Z"
}
```

## 5. Handling Responses
Your application should synchronously wait for the Risk Manager to return its decision.

### Success Response Example (HTTP 200):
```json
{
  "transaction_id": "txn_8008135",
  "correlation_id": "a4d3-8bf...",
  "ml_probability": 0.97,
  "final_score": 97.0,
  "risk_level": "CRITICAL",
  "policy_action": "BLOCK_MERCHANT",
  "execution_status": "HUMAN_APPROVAL_REQUIRED",
  "rule_signals": ["High Risk Context"]
}
```

### 6. Recommended Action Implementation
Your company's application is ultimately responsible for executing the business logic:
- If `policy_action` is `ALLOW`, commit the transaction to your database.
- If `policy_action` is `BLOCK_MERCHANT`, reject the user's attempt with a generalized failure message and do NOT commit the transaction.
- If `execution_status` is `IDEMPOTENT_DUPLICATE`, gracefully ignore the request, as it was already submitted and handled.

### 7. Failure Handling
The Risk Manager employs a strictly **Fail-Closed** design. 
If you receive HTTP 429, 503, 401, or a network timeout, you MUST assume the transaction is **unsafe** and **block** or queue it for review. Do not blindly `ALLOW` the transaction if the Risk Manager is unreachable.
