"""Retry helpers with exponential backoff."""

from __future__ import annotations

import functools
import time
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Call *func*, retrying on *exceptions* with exponential backoff.

    Delay before attempt ``n`` (0-based, after a failure) is
    ``base_delay * 2**n``. ``base_delay=0`` disables sleeping (useful
    in tests). The last exception is raised after *max_attempts*
    attempts in total.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    last_exc: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions as exc:  # noqa: BLE001 - re-raised below
            last_exc = exc
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            if delay > 0:
                time.sleep(delay)
    # Unreachable when max_attempts >= 1, but keep type checkers happy.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_with_backoff: no attempts were made")


def retry(_func: F | None = None, **kwargs):
    """Decorator applying :func:`retry_with_backoff` to a function.

    Usable as ``@retry``, ``@retry()`` or
    ``@retry(max_attempts=5, base_delay=0.5)``.
    """
    max_attempts = kwargs.get("max_attempts", 3)
    base_delay = kwargs.get("base_delay", 1.0)
    exceptions = kwargs.get("exceptions", (Exception,))

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return retry_with_backoff(
                lambda: func(*args, **kw),
                max_attempts=max_attempts,
                base_delay=base_delay,
                exceptions=exceptions,
            )

        return wrapper  # type: ignore[return-value]

    if _func is not None and callable(_func):
        return decorator(_func)
    return decorator
