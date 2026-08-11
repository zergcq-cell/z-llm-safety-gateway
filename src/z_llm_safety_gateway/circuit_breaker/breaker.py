"""Circuit breaker state machine for detector fault tolerance.

Implements a three-state circuit breaker (CLOSED / OPEN / HALF_OPEN) that
protects detectors from cascading failures by short-circuiting calls when
a detector is repeatedly failing, then allowing a controlled probe request
after a recovery timeout.

State transitions::

    CLOSED ──(failures >= threshold)──► OPEN
    OPEN ──(recovery_timeout elapsed)──► HALF_OPEN
    HALF_OPEN ──(success)──► CLOSED
    HALF_OPEN ──(failure)──► OPEN
"""

from __future__ import annotations

import enum
import time

import structlog

logger = structlog.get_logger(__name__)


class CircuitState(enum.Enum):
    """The three states of the circuit breaker state machine."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """A three-state circuit breaker for a single detector.

    The breaker tracks consecutive failures and transitions between CLOSED,
    OPEN, and HALF_OPEN states.  It is **not** thread-safe; callers running
    detectors concurrently should guard access with an ``asyncio.Lock`` or
    similar synchronisation primitive.

    Args:
        failure_threshold: Number of consecutive failures required to trip
            the breaker from CLOSED to OPEN.
        recovery_timeout: Seconds to wait in OPEN state before allowing a
            probe request (transition to HALF_OPEN).
        fallback_action: Action to take when the breaker is OPEN and a call
            is rejected.  ``"fail_open"`` skips the detector; ``"fail_closed"``
            blocks the request.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        fallback_action: str = "fail_open",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._fallback_action = fallback_action

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float | None = None

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current breaker state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self._failure_count

    @property
    def last_failure_time(self) -> float | None:
        """Monotonic timestamp of the last recorded failure, or ``None``."""
        return self._last_failure_time

    @property
    def failure_threshold(self) -> int:
        """Configured failure threshold."""
        return self._failure_threshold

    @property
    def recovery_timeout(self) -> float:
        """Configured recovery timeout in seconds."""
        return self._recovery_timeout

    @property
    def fallback_action(self) -> str:
        """Configured fallback action (``fail_open`` or ``fail_closed``)."""
        return self._fallback_action

    # ------------------------------------------------------------------
    # State-machine operations
    # ------------------------------------------------------------------

    def before_call(self) -> bool:
        """Check whether a detector call should be allowed.

        Returns:
            ``True`` if the call is allowed, ``False`` if the breaker is
            OPEN and the recovery timeout has not yet elapsed.

        State transitions performed by this method:
            - OPEN → HALF_OPEN when *recovery_timeout* has elapsed.
        """
        if self._state is CircuitState.CLOSED:
            return True

        if self._state is CircuitState.OPEN:
            # Defensive: last_failure_time is always set before entering OPEN,
            # but guard against the impossible None case for type safety.
            if self._last_failure_time is None:
                return False
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False

        # HALF_OPEN — allow a single probe request.
        return True

    def record_success(self) -> None:
        """Record a successful detector call.

        Resets ``failure_count`` to 0.  If the breaker was HALF_OPEN, it
        transitions back to CLOSED.
        """
        self._failure_count = 0
        if self._state is CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        """Record a failed detector call.

        Increments ``failure_count``, updates ``last_failure_time``, and
        transitions to OPEN when:
            - In CLOSED: ``failure_count`` reaches ``failure_threshold``.
            - In HALF_OPEN: any single failure re-opens the breaker.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state is CircuitState.CLOSED:
            if self._failure_count >= self._failure_threshold:
                self._transition(CircuitState.OPEN)
        elif self._state is CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)

    def is_open(self) -> bool:
        """Return ``True`` when the breaker is in the OPEN state."""
        return self._state is CircuitState.OPEN

    def reset(self) -> None:
        """Reset the breaker to CLOSED with zeroed counters.

        Useful for testing or manual recovery operations.
        """
        previous = self._state
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        if previous is not CircuitState.CLOSED:
            logger.info(
                "circuit_breaker_reset",
                from_state=previous.value,
                to_state=CircuitState.CLOSED.value,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, new_state: CircuitState) -> None:
        """Perform a state transition and log it."""
        old_state = self._state
        self._state = new_state
        logger.info(
            "circuit_breaker_state_transition",
            from_state=old_state.value,
            to_state=new_state.value,
            failure_count=self._failure_count,
            failure_threshold=self._failure_threshold,
        )
