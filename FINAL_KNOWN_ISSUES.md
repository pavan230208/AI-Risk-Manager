# FINAL KNOWN ISSUES

## 1. Legacy Data Compatibility
The `Transaction` table's `tenant_id` column remains `nullable=True`. This is intentional for this current phase to allow legacy global demo keys to function unhindered without crashing DB constraints. 
**Fix Required for Production:** Once full integration pipelines shift to strictly multi-tenant keys, this column must be hardened via `nullable=False` in an Alembic migration.

## 2. Admin UI for Self-Service API Keys
Currently, generating an API key for a new Tenant is a backend database task (`generate_key_pair` in python). The frontend dashboard lacks an administrative UI page to click "Generate Webhook Secret". 
**Fix Required for Production:** A frontend React view invoking a secured backend router for Tenant Key Management.

## 3. Synthetic Data Bounds
The Random Forest model and associated Precision/Recall metrics are bound to the limitations of the generated synthetic dataset. 
**Fix Required for Production:** Refitting the `.joblib` model using real historical transaction streams.
