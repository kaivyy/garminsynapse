"""Garmin API rate-limiting throttler and pacing engine."""
import logging
import random
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GarminRateLimitError(Exception):
    """Raised when Garmin API rate limits (HTTP 429) requests."""
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class Throttler:
    """Thread-safe rate limiter and pacing controller for Garmin API calls."""

    _rate_limited_until: Optional[float] = None
    _lock = threading.Lock()

    @classmethod
    def mark_rate_limited(cls, cooldown_seconds: float = 60.0, retry_after: Optional[float] = None) -> None:
        """Mark the client as rate-limited until now + cooldown_seconds."""
        duration = retry_after if retry_after is not None else cooldown_seconds
        with cls._lock:
            cls._rate_limited_until = time.time() + duration
        logger.warning(
            f"Garmin API rate-limit triggered. Cooldown active for {duration:.1f}s."
        )

    @classmethod
    def is_rate_limited(cls) -> bool:
        """Check if rate-limiting cooldown is currently active."""
        with cls._lock:
            if cls._rate_limited_until is None:
                return False
            if time.time() >= cls._rate_limited_until:
                cls._rate_limited_until = None
                return False
            return True

    @classmethod
    def get_remaining_cooldown(cls) -> float:
        """Return the number of seconds remaining in active cooldown, or 0.0."""
        with cls._lock:
            if cls._rate_limited_until is None:
                return 0.0
            remaining = cls._rate_limited_until - time.time()
            if remaining <= 0:
                cls._rate_limited_until = None
                return 0.0
            return remaining

    @classmethod
    def ensure_not_rate_limited(cls) -> None:
        """Raise GarminRateLimitError if client is within rate-limit cooldown window."""
        remaining = cls.get_remaining_cooldown()
        if remaining > 0:
            raise GarminRateLimitError(
                f"Rate limited by Garmin Connect. Cooldown active for {remaining:.1f}s.",
                retry_after=remaining,
            )

    @classmethod
    def reset(cls) -> None:
        """Reset rate limiter state."""
        with cls._lock:
            cls._rate_limited_until = None

    @classmethod
    def adaptive_sleep(cls, min_s: float = 1.0, max_s: float = 2.0) -> None:
        """Sleep with randomized jitter to emulate organic traffic."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
