"""Thread-safe rate limiter."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Enforce a minimum interval between calls.

    :param min_interval_seconds: minimum seconds between successive
        :meth:`acquire` calls. ``acquire()`` sleeps only if the last
        call was too recent; the first call never sleeps.
    """

    def __init__(self, min_interval_seconds: float = 1.0):
        self.min_interval_seconds = float(min_interval_seconds)
        self._lock = threading.Lock()
        self._last_call: float | None = None

    def acquire(self) -> None:
        """Block until at least ``min_interval_seconds`` has elapsed
        since the previous :meth:`acquire` call, then record this call."""
        with self._lock:
            now = time.monotonic()
            if self._last_call is not None:
                elapsed = now - self._last_call
                wait = self.min_interval_seconds - elapsed
                if wait > 0:
                    time.sleep(wait)
                    now = time.monotonic()
            self._last_call = now
