import logging
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timezone
import uuid
import traceback

logger = logging.getLogger(__name__)

class EventSchema:
    def __init__(self, event_id: str, event_type: str, correlation_id: str, payload: dict, producer: str, version: str = "1.0"):
        self.event_id = event_id or str(uuid.uuid4())
        self.event_type = event_type
        self.correlation_id = correlation_id
        self.payload = payload
        self.producer = producer
        self.version = version
        self.timestamp = datetime.now(timezone.utc).isoformat()
        
    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
            "producer": self.producer,
            "version": self.version,
            "timestamp": self.timestamp
        }

from abc import ABC, abstractmethod

class EventBus(ABC):
    """
    Stable interface for the event bus.
    Business layer must depend ONLY on this interface.
    """
    @abstractmethod
    def subscribe(self, event_type: str, callback: Callable):
        pass

    @abstractmethod
    def publish(self, event: EventSchema) -> bool:
        pass

    @abstractmethod
    def acknowledge(self, event_id: str):
        pass

    @abstractmethod
    def reject(self, event_id: str, reason: str):
        pass

    @abstractmethod
    def send_to_dlq(self, event_dict: dict, error_trace: str, retry_count: int, first_failure: str = None):
        pass

    @abstractmethod
    def get_recent_events(self, limit: int = 20) -> List[dict]:
        pass

    @abstractmethod
    def get_dlq_count(self) -> int:
        pass


class InMemoryEventBus(EventBus):
    """
    Development Event Bus (In-Memory).
    To be replaced by Kafka/RabbitMQ in production.
    """
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.processed_events = set()
        self.dead_letters = []
        self.event_log = []
        self.max_retries = 3

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        logger.info(f"Subscribed handler to {event_type}")

    def publish(self, event: EventSchema) -> bool:
        """
        Publishes a structured event. Handles idempotency and triggers subscribers.
        """
        if event.event_id in self.processed_events:
            logger.warning(f"[IDEMPOTENCY] Event {event.event_id} already processed. Dropping duplicate.")
            return False
            
        self.processed_events.add(event.event_id)
        event_dict = event.to_dict()
        
        # Schema version check
        if event.version not in ["1.0"]:
            logger.critical(f"[REJECTED] Unsupported event schema version: {event.version}")
            self.send_to_dlq(event_dict, "Unsupported schema version", 0)
            return False
        
        # Structured Logging
        logger.info(f"[PUBLISH] {event.event_type} | ID: {event.event_id} | CorrID: {event.correlation_id} | Prod: {event.producer}")
        self.event_log.append(event_dict)
        
        if event.event_type not in self.subscribers or not self.subscribers[event.event_type]:
            logger.critical(f"[REJECTED] Unknown event type or no handlers: {event.event_type}")
            self.send_to_dlq(event_dict, f"Unknown event type: {event.event_type}", 0)
            return False
            
        for callback in self.subscribers[event.event_type]:
            self._execute_with_retry(callback, event_dict)
            
        return True

    def acknowledge(self, event_id: str):
        # In-memory inherently ACKs on success
        pass

    def reject(self, event_id: str, reason: str):
        # Simulates a manual reject to DLQ
        pass

    def _execute_with_retry(self, callback: Callable, event_dict: dict):
        """
        Executes a subscriber callback with retry logic and dead-letter queue routing.
        """
        first_failure = None
        for attempt in range(1, self.max_retries + 1):
            try:
                callback(event_dict)
                self.acknowledge(event_dict["event_id"])
                return  # Success
            except Exception as e:
                if not first_failure:
                    first_failure = datetime.now(timezone.utc).isoformat()
                logger.error(f"[HANDLER ERROR] Attempt {attempt}/{self.max_retries} failed for event {event_dict['event_id']}: {e}")
                if attempt == self.max_retries:
                    self.send_to_dlq(event_dict, traceback.format_exc(), attempt, first_failure)
                    self.reject(event_dict["event_id"], "Retry exhaustion")

    def send_to_dlq(self, event_dict: dict, error_trace: str, retry_count: int, first_failure: str = None):
        last_failure = datetime.now(timezone.utc).isoformat()
        reason = error_trace.strip().splitlines()[-1] if error_trace else "Unknown rejection"
        logger.critical(f"[DEAD LETTER] Routing event {event_dict['event_id']} to DLQ. Reason: {reason}")
        dlq_entry = {
            "event_id": event_dict.get("event_id"),
            "event_type": event_dict.get("event_type"),
            "correlation_id": event_dict.get("correlation_id"),
            "producer": event_dict.get("producer"),
            "payload_reference": event_dict.get("payload"),
            "failure_reason": reason,
            "exception_category": error_trace.split(':')[0] if ':' in error_trace else "Unknown",
            "retry_count": retry_count,
            "first_failure_timestamp": first_failure or last_failure,
            "last_failure_timestamp": last_failure,
            "full_error": error_trace
        }
        self.dead_letters.append(dlq_entry)

    def get_recent_events(self, limit: int = 20) -> List[dict]:
        return self.event_log[-limit:]

    def get_dlq_count(self) -> int:
        return len(self.dead_letters)

def get_event_bus() -> EventBus:
    import os
    from app.core.config import settings
    
    backend = os.environ.get("EVENT_BUS_BACKEND", "inmemory").lower()
    
    if settings.ENVIRONMENT == "production" and backend != "redis":
        raise RuntimeError("Production requires EVENT_BUS_BACKEND=redis")
        
    if backend == "redis":
        from app.core.redis_events import RedisEventBus
        # Enable fakeredis for local testing if requested
        os.environ["USE_FAKEREDIS"] = os.environ.get("USE_FAKEREDIS", "1")
        return RedisEventBus()
    
    return InMemoryEventBus()

# Global instance for local development
bus = get_event_bus()
