"""Unit tests for CircuitBreaker — TC-CB-001 through TC-CB-009.

Covers the three-state circuit breaker state machine (CLOSED / OPEN / HALF_OPEN)
as specified in spec.yaml and design.md Decision 4.

Time-based transitions (OPEN → HALF_OPEN) are tested using a controllable fake
clock instead of real sleeps, ensuring fast and deterministic test execution.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from z_llm_safety_gateway.circuit_breaker import CircuitBreaker, CircuitState

# Patch target for time.monotonic inside the breaker module.
_MONOTONIC_TARGET = "z_llm_safety_gateway.circuit_breaker.breaker.time.monotonic"


class _FakeClock:
    """A controllable monotonic clock for testing time-based logic.

    Returns ``current_time`` on each call and can be advanced manually via
    :meth:`advance`, eliminating the need for real ``time.sleep``.
    """

    def __init__(self, current_time: float = 1000.0) -> None:
        self._current_time = current_time

    def __call__(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        """Advance the clock by *seconds*."""
        self._current_time += seconds


# ---------------------------------------------------------------------------
# TC-CB-001: Initial state is CLOSED
# ---------------------------------------------------------------------------


def test_initial_state_is_closed() -> None:
    """TC-CB-001: A newly created CircuitBreaker starts in the CLOSED state.

    GIVEN a new CircuitBreaker with default parameters
    WHEN it is instantiated
    THEN state SHALL be CLOSED
    AND failure_count SHALL be 0
    AND last_failure_time SHALL be None
    """
    breaker = CircuitBreaker()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.last_failure_time is None


# ---------------------------------------------------------------------------
# TC-CB-002: CLOSED → OPEN on consecutive threshold failures
# ---------------------------------------------------------------------------


def test_closed_to_open_on_threshold_failures() -> None:
    """TC-CB-002: Consecutive failures reaching the threshold trip the breaker.

    GIVEN a CircuitBreaker with failure_threshold=5 in CLOSED state
    WHEN record_failure() is called 5 times consecutively
    THEN state SHALL transition from CLOSED to OPEN
    AND failure_count SHALL be 5
    AND last_failure_time SHALL be set (not None)
    """
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)

    # First 4 failures — still CLOSED
    for i in range(4):
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == i + 1

    # 5th failure — trips to OPEN
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 5
    assert breaker.last_failure_time is not None


# ---------------------------------------------------------------------------
# TC-CB-003: record_success resets failure_count
# ---------------------------------------------------------------------------


def test_record_success_resets_failure_count() -> None:
    """TC-CB-003: A success resets the consecutive failure count in CLOSED state.

    GIVEN a CircuitBreaker in CLOSED state with failure_count=3
    WHEN record_success() is called
    THEN failure_count SHALL reset to 0
    AND state SHALL remain CLOSED
    """
    breaker = CircuitBreaker(failure_threshold=5)

    for _ in range(3):
        breaker.record_failure()
    assert breaker.failure_count == 3

    breaker.record_success()

    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# TC-CB-004: OPEN state before_call returns False (recovery_timeout not elapsed)
# ---------------------------------------------------------------------------


def test_open_before_call_returns_false_when_timeout_not_elapsed() -> None:
    """TC-CB-004: before_call() rejects calls while OPEN and timeout not elapsed.

    GIVEN a CircuitBreaker in OPEN state with recovery_timeout=30s
    WHEN before_call() is called before 30s have elapsed
    THEN before_call() SHALL return False
    AND state SHALL remain OPEN
    """
    clock = _FakeClock(1000.0)

    with patch(_MONOTONIC_TARGET, side_effect=clock):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Advance only 10 seconds — not enough to recover
        clock.advance(10.0)
        result = breaker.before_call()

    assert result is False
    assert breaker.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# TC-CB-005: OPEN → HALF_OPEN when recovery_timeout elapsed
# ---------------------------------------------------------------------------


def test_open_to_half_open_when_timeout_elapsed() -> None:
    """TC-CB-005: before_call() transitions OPEN → HALF_OPEN after timeout.

    GIVEN a CircuitBreaker in OPEN state with recovery_timeout=30s
    WHEN before_call() is called after 30s have elapsed
    THEN state SHALL transition from OPEN to HALF_OPEN
    AND before_call() SHALL return True (probe request allowed)
    """
    clock = _FakeClock(1000.0)

    with patch(_MONOTONIC_TARGET, side_effect=clock):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Advance 31 seconds — past the recovery timeout
        clock.advance(31.0)
        result = breaker.before_call()

    assert result is True
    assert breaker.state == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# TC-CB-006: HALF_OPEN → CLOSED on record_success
# ---------------------------------------------------------------------------


def test_half_open_to_closed_on_success() -> None:
    """TC-CB-006: A successful probe closes the breaker.

    GIVEN a CircuitBreaker in HALF_OPEN state
    WHEN record_success() is called (probe request succeeded)
    THEN state SHALL transition from HALF_OPEN to CLOSED
    AND failure_count SHALL reset to 0
    """
    clock = _FakeClock(1000.0)

    with patch(_MONOTONIC_TARGET, side_effect=clock):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            breaker.record_failure()
        clock.advance(31.0)
        assert breaker.before_call() is True
        assert breaker.state == CircuitState.HALF_OPEN

    breaker.record_success()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


# ---------------------------------------------------------------------------
# TC-CB-007: HALF_OPEN → OPEN on record_failure
# ---------------------------------------------------------------------------


def test_half_open_to_open_on_failure() -> None:
    """TC-CB-007: A failed probe re-opens the breaker.

    GIVEN a CircuitBreaker in HALF_OPEN state
    WHEN record_failure() is called (probe request failed)
    THEN state SHALL transition from HALF_OPEN back to OPEN
    AND last_failure_time SHALL be updated to the current time
    """
    clock = _FakeClock(1000.0)

    with patch(_MONOTONIC_TARGET, side_effect=clock):
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        for _ in range(3):
            breaker.record_failure()
        clock.advance(31.0)
        assert breaker.before_call() is True
        assert breaker.state == CircuitState.HALF_OPEN

        old_failure_time = breaker.last_failure_time

        clock.advance(5.0)
        breaker.record_failure()

    assert breaker.state == CircuitState.OPEN
    assert breaker.last_failure_time is not None
    assert breaker.last_failure_time != old_failure_time


# ---------------------------------------------------------------------------
# TC-CB-008: is_open() returns True when OPEN
# ---------------------------------------------------------------------------


def test_is_open_returns_true_when_open() -> None:
    """TC-CB-008: is_open() correctly reflects the OPEN state.

    GIVEN a CircuitBreaker
    WHEN the breaker is in OPEN state
    THEN is_open() SHALL return True
    AND WHEN the breaker is in CLOSED state
    THEN is_open() SHALL return False
    """
    breaker = CircuitBreaker(failure_threshold=2)

    # CLOSED state
    assert breaker.is_open() is False

    # Trip to OPEN
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.is_open() is True


# ---------------------------------------------------------------------------
# TC-CB-009: Different configuration parameters are independent
# ---------------------------------------------------------------------------


def test_different_config_parameters_independent() -> None:
    """TC-CB-009: Breakers with different configs behave independently.

    GIVEN two CircuitBreaker instances with different parameters:
      detector_a: failure_threshold=3, recovery_timeout=10, fallback_action=fail_closed
      detector_b: failure_threshold=5, recovery_timeout=30, fallback_action=fail_open
    WHEN both experience failures
    THEN each SHALL trip at its own threshold
    AND each SHALL expose its own configured parameters
    AND one breaker's state SHALL NOT affect the other's
    """
    breaker_a = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=10.0,
        fallback_action="fail_closed",
    )
    breaker_b = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=30.0,
        fallback_action="fail_open",
    )

    # Verify configured parameters are accessible
    assert breaker_a.failure_threshold == 3
    assert breaker_a.recovery_timeout == 10.0
    assert breaker_a.fallback_action == "fail_closed"

    assert breaker_b.failure_threshold == 5
    assert breaker_b.recovery_timeout == 30.0
    assert breaker_b.fallback_action == "fail_open"

    # breaker_a trips after 3 failures
    for _ in range(3):
        breaker_a.record_failure()
    assert breaker_a.state == CircuitState.OPEN

    # breaker_b still CLOSED after only 3 failures (needs 5)
    for _ in range(3):
        breaker_b.record_failure()
    assert breaker_b.state == CircuitState.CLOSED
    assert breaker_b.failure_count == 3

    # breaker_b trips after 2 more failures (total 5)
    breaker_b.record_failure()
    breaker_b.record_failure()
    assert breaker_b.state == CircuitState.OPEN

    # breaker_a's OPEN state is independent of breaker_b
    assert breaker_a.is_open() is True
    assert breaker_b.is_open() is True

    # Resetting breaker_a does not affect breaker_b
    breaker_a.reset()
    assert breaker_a.state == CircuitState.CLOSED
    assert breaker_a.is_open() is False
    assert breaker_b.is_open() is True


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_before_call_returns_true_in_closed_state() -> None:
    """before_call() always allows calls when the breaker is CLOSED."""

    breaker = CircuitBreaker()
    assert breaker.before_call() is True


def test_before_call_returns_true_in_half_open_state() -> None:
    """before_call() allows a probe request when the breaker is HALF_OPEN."""

    clock = _FakeClock(1000.0)

    with patch(_MONOTONIC_TARGET, side_effect=clock):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        clock.advance(31.0)
        assert breaker.before_call() is True  # OPEN → HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

        # HALF_OPEN allows probe
        result = breaker.before_call()
        assert result is True


def test_reset_restores_closed_state() -> None:
    """reset() returns the breaker to CLOSED with zeroed counters."""

    breaker = CircuitBreaker(failure_threshold=2)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    breaker.reset()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.last_failure_time is None
    assert breaker.is_open() is False


@pytest.mark.parametrize(
    ("threshold", "num_failures", "expected_state"),
    [
        (5, 4, CircuitState.CLOSED),  # below threshold — stays closed
        (5, 5, CircuitState.OPEN),  # at threshold — trips
        (5, 6, CircuitState.OPEN),  # above threshold — stays open
        (1, 1, CircuitState.OPEN),  # threshold of 1 — trips on first failure
        (10, 9, CircuitState.CLOSED),  # below threshold — stays closed
        (10, 10, CircuitState.OPEN),  # at threshold — trips
    ],
)
def test_threshold_boundary(
    threshold: int,
    num_failures: int,
    expected_state: CircuitState,
) -> None:
    """Parametrized: breaker trips exactly at failure_threshold, not before."""

    breaker = CircuitBreaker(failure_threshold=threshold)
    for _ in range(num_failures):
        breaker.record_failure()
    assert breaker.state == expected_state
