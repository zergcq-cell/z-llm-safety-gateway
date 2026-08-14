"""In-memory token bucket for rate limiting.

Implements a token-bucket variant where ``rate`` tokens are added per second
(up to ``burst`` capacity) and each request consumes one token.  When the
bucket is empty, requests are rejected until tokens replenish.

Concurrency: ``consume`` is guarded by an ``asyncio.Lock`` so concurrent
event-loop tasks cannot over-consume tokens or drive the count negative.
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """A token bucket with continuous refill and burst capacity.

    Args:
        rate: Tokens added per second (replenishment rate).
        burst: Maximum number of tokens the bucket can hold (capacity).
    """

    def __init__(self, rate: float, burst: int) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst <= 0:
            raise ValueError("burst must be positive")
        self._rate: float = float(rate)
        self._burst: int = int(burst)
        self._tokens: float = float(burst)
        self._last_refill: float = time.monotonic()
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def tokens(self) -> float:
        """Current number of available (not yet consumed) tokens."""
        return self._tokens

    def _refill(self) -> None:
        """Add tokens accrued since the last refill, capped at burst."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(float(self._burst), self._tokens + elapsed * self._rate)
            self._last_refill = now

    async def consume(self, amount: int = 1) -> bool:
        """Try to consume *amount* tokens.

        Returns:
            ``True`` if the tokens were available and consumed, ``False``
            otherwise (no tokens consumed on failure).
        """
        async with self._lock:
            self._refill()
            if self._tokens >= amount:
                self._tokens -= amount
                return True
            return False

    def retry_after(self, amount: int = 1) -> float:
        """Seconds until *amount* tokens become available (``0`` if available).

        Note:
            Best-effort estimate based on the current token count; intended
            for reporting a suggested delay after a rejection.
        """
        deficit = amount - self._tokens
        if deficit <= 0:
            return 0.0
        return deficit / self._rate
