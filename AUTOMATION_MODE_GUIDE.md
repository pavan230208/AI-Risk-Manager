# AUTOMATION MODE GUIDE

## Core Modes of Operation

### 1. Manual Mode
- **Use Case:** A fraud analyst or end-user submits a transaction via the frontend dashboard.
- **Flow:** User -> Frontend -> `POST /api/v1/evaluate` -> Risk Engine.
- **Behavior:** Evaluates the risk and immediately returns the result to the dashboard. Does NOT automatically trigger enterprise webhooks or automated ingestion logic.

### 2. Automated Mode
- **Use Case:** A fintech company or payment gateway automatically routes 10,000 transactions a day to the platform.
- **Flow:** External Provider -> `POST /api/v1/webhooks/transactions` -> Normalizer -> Risk Engine -> ActionExecutor -> EventBus.
- **Behavior:** The system independently ingests, evaluates, blocks, or allows the transaction.

## Operational Controls

- **Automation State Switch:** An admin can toggle Automation ON or OFF via the UI. When OFF, the API strictly rejects incoming enterprise webhooks (403 Forbidden), guaranteeing manual control.
- **Kill Switch:** Superior to Automation. If Automation is ON but Kill Switch is ACTIVATED, all incoming automated transactions are intercepted at the ActionExecutor boundary and `BLOCKED` safely.

## Demonstration Guidelines
Do NOT use hardcoded UI buttons labeled "SAFE" or "BLOCK" for the demo. Instead:
1. Turn Automation ON.
2. Hit the API via Postman/CURL (or the internal UI test-data generator).
3. Watch the system independently classify the payload and surface the result on the System Trace panel dynamically.
