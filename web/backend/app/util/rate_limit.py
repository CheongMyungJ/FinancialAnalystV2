from __future__ import annotations

import asyncio
import time
from threading import Lock


class RateLimitError(RuntimeError):
    pass


class SyncRateLimiter:
    """
    Process-wide simple limiter: ensures at least `min_interval_s` between calls.
    Thread-safe.
    """

    def __init__(self, *, min_interval_s: float) -> None:
        self._min_interval_s = float(min_interval_s)
        self._lock = Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._min_interval_s <= 0:
            return
        with self._lock:
            now = time.monotonic()
            sleep_s = self._next_allowed - now
            if sleep_s > 0:
                time.sleep(sleep_s)
            self._next_allowed = time.monotonic() + self._min_interval_s


class AsyncRateLimiter:
    """
    Async simple limiter: ensures at least `min_interval_s` between calls.
    """

    def __init__(self, *, min_interval_s: float) -> None:
        self._min_interval_s = float(min_interval_s)
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def wait(self) -> None:
        if self._min_interval_s <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            sleep_s = self._next_allowed - now
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)
            self._next_allowed = time.monotonic() + self._min_interval_s

