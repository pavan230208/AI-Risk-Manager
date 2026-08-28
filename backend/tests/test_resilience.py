import pytest
import time
from app.resilience.circuit_breaker import CircuitBreaker, CircuitBreakerOpenException, with_timeout, TimeoutException
from app.resilience.kill_switch import SystemState, SystemModes

def test_circuit_breaker_normal_operation():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=1)
    
    def success_call():
        return "OK"
        
    assert cb.call(success_call) == "OK"
    assert cb.state == "CLOSED"

def test_circuit_breaker_trips_and_recovers():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=1)
    
    def failing_call():
        raise ConnectionError("DB Dead")
        
    def success_call():
        return "OK"
        
    with pytest.raises(ConnectionError):
        cb.call(failing_call)
        
    with pytest.raises(ConnectionError):
        cb.call(failing_call)
        
    # Circuit is now OPEN
    assert cb.state == "OPEN"
    
    # Next call should raise CircuitBreakerOpenException immediately without running
    with pytest.raises(CircuitBreakerOpenException):
        cb.call(success_call)
        
    # Wait for cooldown
    time.sleep(1.1)
    
    # Should transition to HALF_OPEN, succeed, and go to CLOSED
    assert cb.call(success_call) == "OK"
    assert cb.state == "CLOSED"
    assert cb.failures == 0

def test_with_timeout_decorator():
    @with_timeout(0.5)
    def long_running_task(mock_delay=0):
        return "Done"
        
    # Normal execution
    assert long_running_task(mock_delay=0.1) == "Done"
    
    # Timeout execution
    with pytest.raises(TimeoutException):
        long_running_task(mock_delay=0.6)

def test_kill_switch_states():
    state = SystemState()
    assert state.mode == SystemModes.NORMAL
    
    state.activate_kill_switch("admin_user", "Testing switch")
    assert state.kill_switch_active is True
    assert state.mode == SystemModes.AUTONOMOUS_ACTIONS_DISABLED
    
    # Degraded mode should not override kill switch
    state.set_degraded_mode()
    assert state.mode == SystemModes.AUTONOMOUS_ACTIONS_DISABLED
    
    state.deactivate_kill_switch("admin_user", "Testing done")
    assert state.kill_switch_active is False
    assert state.mode == SystemModes.NORMAL
    
def test_degraded_mode_transitions():
    state = SystemState()
    
    state.set_degraded_mode()
    assert state.mode == SystemModes.DEGRADED
    
    state.recover_normal_mode()
    assert state.mode == SystemModes.NORMAL
