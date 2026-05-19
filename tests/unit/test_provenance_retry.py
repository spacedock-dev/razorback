# ABOUTME: AC-7 — retry with exponential backoff on transient errors.
# ABOUTME: Sleeps are dependency-injected so the test runs in zero wallclock.

import pytest

from razorback.provenance.retry import retry_with_backoff


class _Transient(Exception):
    """Stand-in for anthropic.APIStatusError with status_code == 503."""

    def __init__(self, status: int) -> None:
        self.status_code = status


def _is_transient(exc: Exception) -> bool:
    return isinstance(exc, _Transient) and exc.status_code in (502, 503, 504)


def test_retries_twice_then_succeeds():
    calls = []
    sleeps: list[float] = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _Transient(503)
        return "ok"

    result = retry_with_backoff(
        fn,
        is_transient=_is_transient,
        max_attempts=5,
        base_delay=0.1,
        sleep=lambda s: sleeps.append(s),
    )
    assert result == "ok"
    assert len(calls) == 3
    assert sleeps == [0.1, 0.2]


def test_gives_up_after_max_attempts():
    def fn():
        raise _Transient(503)

    with pytest.raises(_Transient):
        retry_with_backoff(
            fn,
            is_transient=_is_transient,
            max_attempts=3,
            base_delay=0.0,
            sleep=lambda s: None,
        )


def test_non_transient_raises_immediately():
    calls: list[int] = []

    def fn():
        calls.append(1)
        raise ValueError("404 not found")

    with pytest.raises(ValueError):
        retry_with_backoff(
            fn,
            is_transient=_is_transient,
            max_attempts=5,
            base_delay=0.0,
            sleep=lambda s: None,
        )
    assert calls == [1]
