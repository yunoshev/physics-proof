# generated from brief/14 · part 14 owns this file
"""Retry policy: three error classes, never confused (part 14 §4).

Network/transport (no terminal event) retries with exponential backoff
(base 2 s, ×2, jitter, max 3 attempts). Incomplete is its own class —
never retried as network. Failed is never blind-retried: the client
raises it in a shape the loop does not treat as transport.
"""

from __future__ import annotations

import pytest

from src import config
from src.accounting import (
    FailedCallError,
    NetworkError,
    backoff_delay_s,
    classify_terminal,
    should_retry_network,
)


def test_three_classes_never_confused():
    """Each terminal maps to exactly one retry class."""
    assert classify_terminal("response.completed") == "completed"
    assert classify_terminal("response.incomplete") == "incomplete"
    assert classify_terminal("response.failed") == "failed"
    # No terminal event at all: the network class (retriable).
    assert classify_terminal(None) == "network"
    assert classify_terminal("") == "network"
    assert classify_terminal("something-new") == "network"


def test_incomplete_is_not_network():
    """Incomplete must never take the transport retry path."""
    assert classify_terminal("response.incomplete") != "network"
    assert classify_terminal("response.incomplete") == "incomplete"


def test_network_error_is_transient_failed_is_not():
    """The loop retries NetworkError with backoff; never FailedCallError."""
    assert isinstance(NetworkError("died"), ConnectionError)
    assert isinstance(NetworkError("died"), OSError)
    assert not isinstance(FailedCallError("400: bad part"), OSError)
    assert not isinstance(FailedCallError("400: bad part"),
                          ConnectionError)
    # So part 06's TRANSIENT_EXCEPTIONS catches exactly the network class.
    from src.loop.dispatch import TRANSIENT_EXCEPTIONS

    assert isinstance(NetworkError("x"), TRANSIENT_EXCEPTIONS)
    assert not isinstance(FailedCallError("x"), TRANSIENT_EXCEPTIONS)


def test_retry_budget_max_three():
    """Attempts 1–2 retry; after the 3rd the call fails (config: max 3)."""
    assert config.RETRY_MAX_ATTEMPTS == 3
    assert should_retry_network(0) is True
    assert should_retry_network(1) is True
    assert should_retry_network(2) is True
    assert should_retry_network(3) is False
    assert should_retry_network(4) is False


def test_backoff_base_two_doubling_with_jitter():
    """Base 2 s, ×2 per attempt, non-negative jitter only."""
    assert config.RETRY_BASE_DELAY_S == pytest.approx(2.0)
    assert config.RETRY_BACKOFF_MULT == pytest.approx(2.0)
    first = [backoff_delay_s(1) for _ in range(50)]
    second = [backoff_delay_s(2) for _ in range(50)]
    assert all(2.0 <= delay < 3.0 for delay in first)
    assert all(4.0 <= delay < 5.0 for delay in second)
    assert backoff_delay_s(3) >= backoff_delay_s(2) - 1.0
    assert backoff_delay_s(3) >= 8.0
