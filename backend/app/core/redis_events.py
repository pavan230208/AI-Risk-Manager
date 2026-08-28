import os
import json
import logging
import traceback
import uuid
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List
import redis

from app.core.events import EventBus, EventSchema

logger = logging.getLogger(__name__)

class RedisEventBus(EventBus):
    """
    Production Event Bus using Redis Streams.
    Provides durability, consumer groups, backpressure management, and acknowledgment.
    """
    def __init__(self, redis_url: str = None, group_name: str = "risk_consumers", consumer_name: str = None):
        if not redis_url:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            
        # Optional fakeredis support for pure local testing
        if os.environ.get("USE_FAKEREDIS") == "1":
            from app.core.config import settings
            if settings.ENVIRONMENT == "production":
                raise RuntimeError("FakeRedis is not allowed in production.")
            import fakeredis
            self.redis = fakeredis.FakeRedis(decode_responses=True)
            logger.info("Using FakeRedis Event Bus")
        else:
            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
            
        self.group_name = group_name
        self.consumer_name = consumer_name or f"consumer-{uuid.uuid4().hex[:6]}"
        self.subscribers: Dict[str, List[Callable]] = {}
        self.max_retries = 3

    def _ensure_group(self, stream_key: str):
        try:
            self.redis.xgroup_create(stream_key, self.group_name, id="0", mkstream=True)
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise e

    def subscribe(self, event_type: str, callback: Callable):
        stream_key = f"stream:{event_type}"
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
            self._ensure_group(stream_key)
        self.subscribers[event_type].append(callback)
        logger.info(f"[{self.consumer_name}] Subscribed to Redis stream: {stream_key}")

    def publish(self, event: EventSchema) -> bool:
        event_dict = event.to_dict()
        
        # Schema version check
        if event.version not in ["1.0"]:
            logger.critical(f"[REJECTED] Unsupported event schema version: {event.version}")
            self.send_to_dlq(event_dict, "Unsupported schema version", 0)
            return False
            
        stream_key = f"stream:{event.event_type}"
        
        # Fast-fail idempotency check - simplistic set check (in prod we'd use a TTL set)
        if self.redis.sismember("processed_event_ids", event.event_id):
            logger.warning(f"[IDEMPOTENCY] Event {event.event_id} already published. Dropping duplicate.")
            return False
            
        try:
            # We serialize payload as JSON string to store in Redis Hash
            data = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "correlation_id": event.event_id, # Using event_id as message ID implicitly
                "payload": json.dumps(event_dict)
            }
            # Publish to Redis Stream with MAXLEN to prevent infinite growth
            msg_id = self.redis.xadd(stream_key, data, maxlen=10000, approximate=True)
            self.redis.sadd("processed_event_ids", event.event_id)
            logger.info(f"[PUBLISH] {event.event_type} | ID: {event.event_id} | StreamID: {msg_id}")
            return True
        except Exception as e:
            logger.critical(f"[PUBLISH FAILED] Event {event.event_id} failed to publish to Redis: {e}")
            return False

    def acknowledge(self, stream_key: str, message_id: str):
        try:
            self.redis.xack(stream_key, self.group_name, message_id)
        except Exception as e:
            logger.error(f"Failed to ACK {message_id} on {stream_key}: {e}")

    def reject(self, stream_key: str, message_id: str, reason: str):
        # We don't ACK so it stays in pending, but we manually route to DLQ
        self.acknowledge(stream_key, message_id)

    def send_to_dlq(self, event_dict: dict, error_trace: str, retry_count: int, first_failure: str = None):
        last_failure = datetime.now(timezone.utc).isoformat()
        reason = error_trace.strip().splitlines()[-1] if error_trace else "Unknown rejection"
        logger.critical(f"[DEAD LETTER] Routing event {event_dict['event_id']} to DLQ. Reason: {reason}")
        
        dlq_entry = {
            "event_id": event_dict.get("event_id"),
            "event_type": event_dict.get("event_type"),
            "correlation_id": event_dict.get("correlation_id"),
            "producer": event_dict.get("producer"),
            "failure_reason": reason,
            "retry_count": str(retry_count),
            "first_failure_timestamp": first_failure or last_failure,
            "last_failure_timestamp": last_failure,
            "full_error": error_trace,
            "payload_json": json.dumps(event_dict)
        }
        
        try:
            self.redis.xadd("stream:DLQ", dlq_entry, maxlen=10000, approximate=True)
        except Exception as e:
            logger.critical(f"FATAL: Failed to write to DLQ: {e}")

    def get_recent_events(self, limit: int = 20) -> List[dict]:
        try:
            # Fetch recent from known main streams
            events = []
            for stream in ["stream:TransactionEvaluated", "stream:AdminAudit"]:
                try:
                    results = self.redis.xrevrange(stream, max="+", min="-", count=limit)
                    for _, data in results:
                        raw_payload = data.get("payload") if isinstance(data, dict) else data.get(b"payload", b"{}").decode('utf-8')
                        events.append(json.loads(raw_payload))
                except Exception:
                    pass
            # Sort by timestamp descending
            events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return events[:limit]
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []

    def get_dlq_count(self) -> int:
        try:
            return self.redis.xlen("stream:DLQ")
        except Exception:
            return 0

    def replay_dlq(self, batch_size=10):
        """Replay messages from DLQ for debugging or operational recovery."""
        try:
            messages = self.redis.xrange("stream:DLQ", count=batch_size)
            for msg_id, data in messages:
                raw_payload = data.get("payload_json") if isinstance(data, dict) else data.get(b"payload_json").decode('utf-8')
                event_dict = json.loads(raw_payload)
                # Reconstruct event and publish
                evt = EventSchema(**{k:v for k,v in event_dict.items() if k != "timestamp"})
                self.redis.srem("processed_event_ids", evt.event_id) # Remove idempotency lock
                success = self.publish(evt)
                if success:
                    self.redis.xdel("stream:DLQ", msg_id)
        except Exception as e:
            logger.error(f"DLQ Replay failed: {e}")

    def _execute_with_retry(self, callback: Callable, event_dict: dict, stream_key: str, msg_id: str):
        first_failure = None
        for attempt in range(1, self.max_retries + 1):
            try:
                callback(event_dict)
                self.acknowledge(stream_key, msg_id)
                return True
            except Exception as e:
                if not first_failure:
                    first_failure = datetime.now(timezone.utc).isoformat()
                logger.error(f"[HANDLER ERROR] Attempt {attempt}/{self.max_retries} failed for event {event_dict['event_id']}: {e}")
                if attempt == self.max_retries:
                    self.send_to_dlq(event_dict, traceback.format_exc(), attempt, first_failure)
                    self.reject(stream_key, msg_id, "Retry exhaustion")
                    return False
            time.sleep(0.1 * attempt)

    def recover_pending_messages(self, stream_key: str, min_idle_time_ms: int = 5000):
        """Claims and recovers messages from crashed consumers using XPENDING / XCLAIM."""
        try:
            # FakeRedis does not fully support XPENDING/XCLAIM perfectly in all versions, wrapped in try/except
            pending = self.redis.xpending_range(stream_key, self.group_name, "-", "+", 10)
            for msg in pending:
                msg_id = msg['message_id']
                idle_time = msg['time_since_delivered']
                if idle_time >= min_idle_time_ms:
                    # Claim it
                    claimed = self.redis.xclaim(stream_key, self.group_name, self.consumer_name, min_idle_time_ms, [msg_id])
                    # Process claimed messages
                    for c_msg_id, data in claimed:
                        c_msg_id_str = c_msg_id.decode('utf-8') if isinstance(c_msg_id, bytes) else c_msg_id
                        raw_payload = data.get("payload") if isinstance(data, dict) else data.get(b"payload").decode('utf-8')
                        event_dict = json.loads(raw_payload)
                        event_type = event_dict.get("event_type")
                        for callback in self.subscribers.get(event_type, []):
                            self._execute_with_retry(callback, event_dict, stream_key, c_msg_id_str)
        except Exception as e:
            pass # Ignore if Fakeredis doesn't support or if stream doesn't exist

    def consume_once(self, timeout_ms: int = 1000):
        """Polls Redis Streams for subscribed event types."""
        if not self.subscribers:
            return
            
        streams = {f"stream:{et}": ">" for et in self.subscribers.keys()}
        try:
            for stream in streams.keys():
                self.recover_pending_messages(stream)
                
            results = self.redis.xreadgroup(self.group_name, self.consumer_name, streams, count=10, block=timeout_ms)
            for stream, messages in results:
                stream_name = stream.decode('utf-8') if isinstance(stream, bytes) else stream
                event_type = stream_name.replace("stream:", "")
                
                for msg_id, data in messages:
                    msg_id_str = msg_id.decode('utf-8') if isinstance(msg_id, bytes) else msg_id
                    try:
                        raw_payload = data.get("payload") if isinstance(data, dict) else data.get(b"payload").decode('utf-8')
                        event_dict = json.loads(raw_payload)
                        
                        for callback in self.subscribers.get(event_type, []):
                            self._execute_with_retry(callback, event_dict, stream_name, msg_id_str)
                            
                    except Exception as e:
                        logger.critical(f"Failed to parse or route message {msg_id_str}: {e}")
                        self.reject(stream_name, msg_id_str, "Parse Error")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis Connection Error: {e}")
            raise e
