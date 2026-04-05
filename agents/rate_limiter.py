"""
agents/rate_limiter.py — Token bucket rate limiter for LLM API calls.
Prevents hitting provider rate limits and ensures fair usage.
"""
from __future__ import annotations

import threading
import time
from typing import Optional


class TokenBucket:
    """
    Thread-safe token bucket rate limiter.
    Allows burst_size requests immediately, then refills at rate/second.
    """

    def __init__(self, rate: float, burst_size: int):
        self._rate = rate          # tokens per second
        self._burst = burst_size   # max tokens
        self._tokens = float(burst_size)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens. Blocks until available or timeout.
        Returns True if acquired, False if timed out.
        """
        deadline = time.monotonic() + (timeout or float("inf"))
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now


class LLMRateLimiter:
    """
    Per-provider rate limiters for LLM API calls.
    Groq free tier: ~30 req/min, Gemini: ~60 req/min.
    """

    _limiters: dict[str, TokenBucket] = {
        "groq":   TokenBucket(rate=0.5, burst_size=10),   # 30/min
        "gemini": TokenBucket(rate=1.0, burst_size=15),   # 60/min
        "openai": TokenBucket(rate=0.5, burst_size=10),
    }

    @classmethod
    def acquire(cls, provider: str, timeout: float = 30.0) -> bool:
        limiter = cls._limiters.get(provider.lower())
        if not limiter:
            return True  # Unknown provider — don't limit
        return limiter.acquire(timeout=timeout)
