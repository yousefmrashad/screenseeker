import time
import logging
import threading
from functools import wraps
from typing import Any, List, Optional
from google.genai import types, client
import config

logger = logging.getLogger("RateLimiter")
logger.setLevel(logging.INFO)

class TokenBucketLimiter:
    """
    A thread-safe implementation of the Token Bucket rate limiting algorithm.
    """
    def __init__(self, capacity: float, refill_rate_per_sec: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = capacity
        self.last_refill_time = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        if elapsed > 0:
            new_tokens = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill_time = now

    def consume(self, tokens_to_consume: float = 1.0, block: bool = True) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= tokens_to_consume:
                self.tokens -= tokens_to_consume
                return True
            if not block:
                return False
            needed = tokens_to_consume - self.tokens
            sleep_duration = needed / self.refill_rate
            
        logger.warning(f"Rate limit reached. Sleeping for {sleep_duration:.2f}s to refill tokens...")
        time.sleep(sleep_duration)
        
        with self.lock:
            self._refill()
            if self.tokens >= tokens_to_consume:
                self.tokens -= tokens_to_consume
                return True
            else:
                self.tokens = 0.0
                return True


def rate_limited(limiter: TokenBucketLimiter):
    """Decorator to enforce token bucket rate limiting on any function or method."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.consume(1.0, block=True)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Default rate limiter loaded from config
default_limiter = TokenBucketLimiter(
    capacity=config.RATE_LIMIT_CAPACITY,
    refill_rate_per_sec=config.RATE_LIMIT_RPM / 60.0
)


@rate_limited(default_limiter)
def generate_content_limited(
    client: client.Client,
    model: str,
    contents: List[Any],
    config: Optional[types.GenerateContentConfig] = None
) -> Any:
    """
    Invokes the Gemini API generate_content method.
    This is the only function in the application that performs the network request 
    and it contains no other bounded operations.
    """
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )
