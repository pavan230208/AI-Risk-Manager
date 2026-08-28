# MULTI-PLATFORM INTEGRATION GUIDE

## Core Architecture
The Autonomous AI Risk Manager relies on a unified, provider-agnostic backend. Web dashboards, Android mobile apps, iOS clients, and third-party SaaS backends interface with the exact same FastApi JSON endpoints.

## 1. Web Dashboard (Next.js)
**Integration Pattern:** Interactive / State Polling
**Endpoint:** `POST /api/v1/evaluate` (Requires Admin/Analyst JWT)
- **Flow:** User clicks "Analyze", payload is constructed from form state, backend returns JSON risk explanation, UI renders a color-coded card.

## 2. Server-to-Server Webhook (Razorpay / Stripe)
**Integration Pattern:** Event-Driven Webhook
**Endpoint:** `POST /api/v1/webhooks/transactions?provider=razorpay` (Requires API Key)
- **Flow:** Razorpay triggers `payment.captured`. Your backend forwards the payload. The Risk Engine normalizes the Razorpay schema internally, runs risk, blocks if necessary, and logs the outcome.

## 3. Mobile App (Android / iOS)
**Integration Pattern:** Lightweight API Request
**Endpoint:** `POST /api/v1/transactions/evaluate` (Requires API Key)
**Payload Example (Swift/Kotlin mapping):**
```json
{
  "transaction_id": "app_txn_1",
  "user_id": "usr_999",
  "merchant_id": "self",
  "amount": 250.0,
  "currency": "INR",
  "device_id": "ios_device_id",
  "location": "IN",
  "timestamp": "2026-08-28T14:00:00Z"
}
```
- **Flow:** User swipes "Pay". Mobile app fires HTTPS request to Risk Manager. Risk Manager responds with `execution_status`. App allows navigation or throws "Transaction Blocked" error.

## Unified Backend Value
By decoupling the risk logic from the client layer, adding a new platform (e.g., a Desktop POS app) simply involves formatting a generic JSON POST request. No duplicated ML models or Rule Engines are required.
