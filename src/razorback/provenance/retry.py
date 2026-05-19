# ABOUTME: Exponential-backoff retry harness for the provenance resolvers (§6.4).
# ABOUTME: Sleep is dependency-injected so unit tests run in zero wallclock.

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    is_transient: Callable[[Exception], bool],
    max_attempts: int = 5,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `fn` until success or `max_attempts` reached.

    On a transient exception (`is_transient(exc) == True`), sleep
    `base_delay * 2**(attempt-1)` then retry. Non-transient exceptions
    propagate immediately.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_transient(exc):
                raise
            last_exc = exc
            if attempt == max_attempts:
                break
            sleep(base_delay * (2 ** (attempt - 1)))
    assert last_exc is not None
    raise last_exc
