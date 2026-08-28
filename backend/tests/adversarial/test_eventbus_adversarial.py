import pytest
from app.core.events import EventSchema, InMemoryEventBus
import uuid

@pytest.fixture
def bus():
    return InMemoryEventBus()

def test_unknown_event_type(bus):
    event = EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="UnknownEvent",
        correlation_id=str(uuid.uuid4()),
        payload={},
        producer="Test"
    )
    result = bus.publish(event)
    assert result is False
    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0]["failure_reason"] == "Unknown event type: UnknownEvent"

def test_unsupported_schema_version(bus):
    event = EventSchema(
        event_id=str(uuid.uuid4()),
        event_type="TransactionEvaluated",
        correlation_id=str(uuid.uuid4()),
        payload={},
        producer="Test",
        version="999.0"
    )
    result = bus.publish(event)
    assert result is False
    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0]["failure_reason"] == "Unsupported schema version"

def test_duplicate_event_dropped(bus):
    event_id = str(uuid.uuid4())
    event = EventSchema(
        event_id=event_id,
        event_type="TransactionEvaluated",
        correlation_id=str(uuid.uuid4()),
        payload={},
        producer="Test"
    )
    
    bus.subscribe("TransactionEvaluated", lambda e: None)
    
    res1 = bus.publish(event)
    res2 = bus.publish(event)
    
    assert res1 is True
    assert res2 is False # Dropped due to idempotency
