# BUILDATHON DEMO SCRIPT

**Duration: 5–7 minutes**

### 1. Opening
"Hello, we are presenting the Autonomous AI Risk Manager. The fundamental problem in AI fintech today is safety: if you let a Machine Learning model directly authorize transactions, you risk catastrophic unauthorized transfers when the model hallucinates or faces adversarial inputs. Our system solves this by ensuring the AI is strictly an *advisory signal*, governed by a deterministic, fail-closed policy architecture."

### 2. Architecture
"Our architecture is built on FastAPI, Redis, PostgreSQL, and Next.js. Transactions flow through Feature Extraction, an ML Risk Scorer, and then critically, a Deterministic Rule Engine. The Rule Engine has the final say. Before any database write, an Action Executor ensures Redis idempotency to prevent replay attacks."

### 3. SAFE Transaction
*(Action: On the dashboard, click the 'SAFE' preset, then click 'ANALYZE TRANSACTION')*
"Let's simulate a normal $20 transaction from a trusted device. The ML model evaluates a low fraud probability, the Rule Engine finds no hard violations, the Policy Engine allows it, and the Action Executor successfully processes it. Notice the green 'SAFE' status and 'EXECUTED' state."

### 4. SUSPICIOUS Transaction
*(Action: Click 'SUSPICIOUS', then 'ANALYZE TRANSACTION')*
"Now, a $2,500 transaction from a new device in an unusual location. The ML flags a high probability, and the deterministic rules trigger 'new_device_high_amount'. The Policy Engine blocks autonomous execution and flags it as 'CRITICAL'. It requires human review."

### 5. HIGH Transaction
*(Action: Click 'HIGH', then 'ANALYZE TRANSACTION')*
"Here is an $8,000 transaction. Even if the ML model were confident it was safe, our Rule Engine recognizes the extreme amount. The system demands 'HUMAN_APPROVAL_REQUIRED', proving the deterministic safety net overrides the ML."

### 6. CRITICAL Transaction
*(Action: Click 'CRITICAL', then 'ANALYZE TRANSACTION')*
"This is a $50,000 transaction from a compromised device. The deterministic rules instantly block it. Execution is strictly prevented."

### 7. Duplicate Attack
*(Action: Click 'ANALYZE TRANSACTION' rapidly 3 times on the same payload)*
"What happens during a network retry or replay attack? I'm sending the identical transaction multiple times. Notice the Execution Status immediately flips to 'IDEMPOTENT_DUPLICATE'. The Redis distributed lock prevented a double charge before hitting the database."

### 8. Kill Switch
*(Action: Scroll down, click 'ACTIVATE KILL SWITCH')*
"In a worst-case scenario—say, a zero-day exploit or infrastructure degradation—administrators can activate the Kill Switch. This requires strict JWT RBAC authorization."
*(Action: Click 'SAFE', then 'ANALYZE TRANSACTION')*
"Now, even a completely safe $20 transaction is blocked. The system degrades gracefully to 'PENDING_APPROVAL', preventing any autonomous actions."

### 9. System Trace
*(Action: Point to the System Trace / Audit Trail panel)*
"Every action we just took was published to a Redis EventBus. You can see the real-time audit trail here, proving the exact sequence of events, ensuring full compliance and explainability."

### 10. Closing
"In conclusion, we've built a production-grade risk platform. By isolating the ML model behind a deterministic policy layer and fail-closed idempotency, we achieve the speed of AI with the safety of traditional banking infrastructure. Thank you."
