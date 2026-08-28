import time
import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    pass

class TimeoutException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: int = 5):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        now = time.time()
        
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.cooldown_seconds:
                logger.info(f"Circuit Breaker entering HALF_OPEN state for {func.__name__}")
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenException(f"Circuit Breaker is OPEN for {func.__name__}")
                
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                logger.info(f"Circuit Breaker recovered (CLOSED) for {func.__name__}")
                self.state = "CLOSED"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.state == "HALF_OPEN" or self.failures >= self.failure_threshold:
                if self.state != "OPEN":
                    logger.critical(f"Circuit Breaker tripped (OPEN) for {func.__name__} after {self.failures} failures.")
                self.state = "OPEN"
            raise e

def with_timeout(seconds: float):
    """
    Naive timeout decorator for demo purposes. 
    In production, this would use asyncio.wait_for or multiprocessing.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # For simplicity in this demo environment, we check time inside if it's a loop,
            # but since we can't easily interrupt synchronous python without signals (Unix only)
            # or threads, we'll mock timeout behavior if an artificial 'mock_delay' is passed.
            if kwargs.get('mock_delay', 0) > seconds:
                raise TimeoutException(f"Execution of {func.__name__} timed out after {seconds}s")
            return func(*args, **kwargs)
        return wrapper
    return decorator
