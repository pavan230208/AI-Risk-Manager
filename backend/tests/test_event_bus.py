import pytest
import uuid
from app.core.events import InMemoryEventBus, EventSchema

@pytest.fixture
def bus():
    return InMemoryEventBus()

def test_1_2_3_publish_subscribe_delivery(bus):
    received = []
    def handler(evt):
        received.append(evt)
    
    bus.subscribe("TransactionReceived", handler)
    event = EventSchema(event_id="e1", event_type="TransactionReceived", correlation_id="c1", payload={"foo": "bar"}, producer="Test")
    
    assert bus.publish(event) is True
    assert len(received) == 1
    assert received[0]["correlation_id"] == "c1"

def test_4_5_duplicate_idempotent(bus):
    received = []
    def handler(evt):
        received.append(evt)
        
    bus.subscribe("DuplicateTest", handler)
    event = EventSchema(event_id="e_dup", event_type="DuplicateTest", correlation_id="c1", payload={}, producer="Test")
    
    # First publish succeeds
    assert bus.publish(event) is True
    # Second publish drops
    assert bus.publish(event) is False
    assert len(received) == 1

def test_6_malformed_event():
    # Attempting to initialize EventSchema with missing positional args will raise TypeError natively
    with pytest.raises(TypeError):
        EventSchema()

def test_7_unknown_event_type(bus):
    # Publish should be rejected and routed to DLQ
    event = EventSchema(event_id="e_unk", event_type="UnknownType", correlation_id="c1", payload={}, producer="Test")
    assert bus.publish(event) is False
    assert len(bus.dead_letters) == 1
    assert "Unknown event type" in bus.dead_letters[0]["failure_reason"]

def test_schema_version_rejection(bus):
    # Unsupported schema version must be rejected safely
    event = EventSchema(event_id="e_sch", event_type="TransactionReceived", correlation_id="c1", payload={}, producer="Test", version="999.0")
    assert bus.publish(event) is False
    assert len(bus.dead_letters) == 1
    assert "Unsupported schema version" in bus.dead_letters[0]["failure_reason"]

def test_8_9_handler_failure_and_retry(bus):
    attempts = []
    def failing_handler(evt):
        attempts.append(1)
        raise ValueError("Intentional crash")
        
    bus.subscribe("FailTest", failing_handler)
    event = EventSchema(event_id="e_fail", event_type="FailTest", correlation_id="c1", payload={}, producer="Test")
    
    bus.publish(event)
    # Should retry 3 times exactly
    assert len(attempts) == 3
    # Should end up in dead letter queue
    assert len(bus.dead_letters) == 1
    assert bus.dead_letters[0]["event_id"] == "e_fail"
    assert "Intentional crash" in bus.dead_letters[0]["full_error"]

def test_10_correlation_id_propagation(bus):
    received = []
    def handler(evt):
        received.append(evt["correlation_id"])
        
    bus.subscribe("CorrTest", handler)
    event = EventSchema(event_id="e_corr", event_type="CorrTest", correlation_id="SHARED-CORR-123", payload={}, producer="Test")
    bus.publish(event)
    
    assert received[0] == "SHARED-CORR-123"

def test_11_event_ordering(bus):
    received = []
    def handler(evt):
        received.append(evt["payload"]["seq"])
        
    bus.subscribe("SeqTest", handler)
    # Publish sequentially
    bus.publish(EventSchema(event_id="seq1", event_type="SeqTest", correlation_id="c1", payload={"seq": 1}, producer="T"))
    bus.publish(EventSchema(event_id="seq2", event_type="SeqTest", correlation_id="c1", payload={"seq": 2}, producer="T"))
    bus.publish(EventSchema(event_id="seq3", event_type="SeqTest", correlation_id="c1", payload={"seq": 3}, producer="T"))
    
    assert received == [1, 2, 3]

def test_12_multiple_subscribers(bus):
    recv1 = []
    recv2 = []
    bus.subscribe("MultiTest", lambda e: recv1.append(e))
    bus.subscribe("MultiTest", lambda e: recv2.append(e))
    
    bus.publish(EventSchema(event_id="e_multi", event_type="MultiTest", correlation_id="c1", payload={}, producer="T"))
    
    assert len(recv1) == 1
    assert len(recv2) == 1

def test_13_audit_traceability(bus):
    bus.publish(EventSchema(event_id="e_audit", event_type="AuditTest", correlation_id="c_audit", payload={}, producer="T"))
    assert len(bus.event_log) == 1
    assert bus.event_log[0]["event_id"] == "e_audit"
    assert bus.event_log[0]["correlation_id"] == "c_audit"
