from typing import Dict, Any
from app.api.router import TransactionPayload
import uuid
from datetime import datetime, timezone

class ProviderAdapterError(Exception):
    pass

class BaseProviderAdapter:
    def normalize(self, raw_payload: Dict[str, Any]) -> TransactionPayload:
        raise NotImplementedError

class RazorpayAdapter(BaseProviderAdapter):
    def normalize(self, raw_payload: Dict[str, Any]) -> TransactionPayload:
        try:
            # Example Razorpay webhook payload
            # { "event": "payment.captured", "payload": { "payment": { "entity": { "id": "pay_29QQoUBi66xm2f", "amount": 50000, "currency": "INR", "customer_id": "cust_D", "email": "a@b.com", "contact": "99999", "created_at": 1600000000 } } } }
            payment = raw_payload.get("payload", {}).get("payment", {}).get("entity", {})
            if not payment:
                raise ValueError("Missing payment entity")
            
            return TransactionPayload(
                transaction_id=payment.get("id", f"TXN-{uuid.uuid4()}"),
                user_id=payment.get("customer_id", "unknown_user"),
                merchant_id="merchant_self", # Could be extracted from headers or tenant mapping
                amount=payment.get("amount", 0) / 100.0, # Razorpay amounts are in paise
                currency=payment.get("currency", "INR"),
                device_id="unknown_device", # Providers don't always give this
                location="unknown_location",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        except Exception as e:
            raise ProviderAdapterError(f"Razorpay normalization failed: {str(e)}")

class UPIAdapter(BaseProviderAdapter):
    def normalize(self, raw_payload: Dict[str, Any]) -> TransactionPayload:
        try:
            # Example UPI payload
            # { "txnId": "UPI12345", "payerVpa": "user@upi", "payeeVpa": "merchant@upi", "amount": "150.00", "timestamp": "2023-10-01T12:00:00Z" }
            return TransactionPayload(
                transaction_id=raw_payload.get("txnId", f"TXN-{uuid.uuid4()}"),
                user_id=raw_payload.get("payerVpa", "unknown_user"),
                merchant_id=raw_payload.get("payeeVpa", "unknown_merchant"),
                amount=float(raw_payload.get("amount", 0.0)),
                currency="INR", # UPI is typically INR
                device_id="unknown_device",
                location="IN",
                timestamp=raw_payload.get("timestamp", datetime.now(timezone.utc).isoformat())
            )
        except Exception as e:
            raise ProviderAdapterError(f"UPI normalization failed: {str(e)}")

class GenericAdapter(BaseProviderAdapter):
    def normalize(self, raw_payload: Dict[str, Any]) -> TransactionPayload:
        try:
            return TransactionPayload(**raw_payload)
        except Exception as e:
            raise ProviderAdapterError(f"Generic normalization failed: {str(e)}")

class ProviderAdapterFactory:
    @staticmethod
    def get_adapter(provider_name: str) -> BaseProviderAdapter:
        adapters = {
            "razorpay": RazorpayAdapter(),
            "upi": UPIAdapter(),
            "generic": GenericAdapter()
        }
        return adapters.get(provider_name.lower(), GenericAdapter())
