import time
from typing import Callable, Any
from config.redis_cache import get_redis
from services.logging_service import get_logger

logger = get_logger("circuit_breaker")

class CircuitBreaker:
    """
    Redis-backed circuit breaker to protect against downstream API failures.
    Tracks failures per provider and enters 'Open' (Safe) mode if thresholds met.
    """
    def __init__(self, provider_name: str, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.provider = provider_name
        self.threshold = failure_threshold
        self.timeout = recovery_timeout
        self.key = f"cb:fail:{provider_name}"
        self.status_key = f"cb:status:{provider_name}"

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        client = get_redis()
        
        # 1. Check if circuit is open
        if client and client.get(self.status_key):
            logger.warning(f"Circuit for {self.provider} is OPEN. Skipping call.")
            return None

        try:
            result = await func(*args, **kwargs)
            # Clear failures on success
            if client: client.delete(self.key)
            return result
        except Exception as e:
            logger.error(f"Circuit breaker caught error for {self.provider}: {e}")
            
            if client:
                fails = client.incr(self.key)
                if int(fails) == 1:
                    client.expire(self.key, self.timeout)
                
                if int(fails) >= self.threshold:
                    logger.critical(f"Circuit for {self.provider} OPENED due to {fails} failures.")
                    client.set(self.status_key, "open", ex=self.timeout)
            
            raise e

    def is_healthy(self) -> bool:
        client = get_redis()
        if not client: return True
        return not bool(client.get(self.status_key))
