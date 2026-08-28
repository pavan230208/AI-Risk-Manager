import time
import logging
from fastapi import HTTPException
from app.actions.executor import ActionExecutor

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute: int = 1000):
        self.limit = requests_per_minute
        self._executor = ActionExecutor()

    def check_limit(self, client_id: str):
        redis_conn = self._executor._get_redis()
        if not redis_conn:
            # Fail closed
            raise HTTPException(status_code=503, detail="Rate limiter unavailable")

        # Basic fixed window rate limiting
        current_minute = int(time.time() // 60)
        key = f"rate_limit:{client_id}:{current_minute}"
        
        try:
            current_count = redis_conn.incr(key)
            if current_count == 1:
                redis_conn.expire(key, 60)
                
            if current_count > self.limit:
                logger.warning(f"Rate limit exceeded for {client_id}")
                raise HTTPException(status_code=429, detail="Too many requests")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            raise HTTPException(status_code=503, detail="Rate limiter error")

rate_limiter = RateLimiter()
