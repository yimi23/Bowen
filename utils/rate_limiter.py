"""
utils/rate_limiter.py — Token bucket rate limiter.
Prevents exhausting API quotas and runaway billing.
"""

import asyncio
import time
from collections import deque


class RateLimiter:
    """
    Sliding window rate limiter.
    Tracks timestamps of the last N calls; sleeps if the window is full.
    """

    def __init__(self, max_calls: int, window_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Call before every API request. Sleeps if rate limit would be exceeded."""
        async with self._lock:
            now = time.monotonic()
            # Drop timestamps outside the window
            while self._timestamps and self._timestamps[0] < now - self.window:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_calls:
                # Sleep until the oldest call falls out of the window
                sleep_for = self.window - (now - self._timestamps[0]) + 0.01
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # Re-prune after sleep
                now = time.monotonic()
                while self._timestamps and self._timestamps[0] < now - self.window:
                    self._timestamps.popleft()

            self._timestamps.append(time.monotonic())

    def reset(self) -> None:
        self._timestamps.clear()


# Shared limiters — one per API backend
# Anthropic: 50 req/min on standard tier (we use 30 to be safe)
anthropic_limiter = RateLimiter(max_calls=30, window_seconds=60)

# Groq: 30 req/min on free tier
groq_limiter = RateLimiter(max_calls=25, window_seconds=60)

# Tavily: 100 req/min; 200 searches/month free
tavily_limiter = RateLimiter(max_calls=10, window_seconds=60)
