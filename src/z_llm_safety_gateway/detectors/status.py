"""Application-scoped detector lifecycle state and policy snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from threading import RLock
from typing import Any, Literal

DetectorDirection = Literal["input", "output"]


class DetectorState(str, Enum):
    """Lifecycle states shared by startup, readiness, audit, and metrics."""

    CONFIGURED = "configured"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"
    UNHEALTHY = "unhealthy"


class DetectorReasonCode(str, Enum):
    """Stable, non-sensitive failure reasons safe for external signals."""

    INITIALIZATION_ERROR = "initialization_error"
    HEALTH_CHECK_ERROR = "health_check_error"
    HEALTH_CHECK_TIMEOUT = "health_check_timeout"
    HEALTH_CHECK_FAILED = "health_check_failed"


@dataclass(frozen=True, slots=True)
class DetectorStatus:
    """Immutable snapshot for one configured detector direction."""

    direction: DetectorDirection
    name: str
    detector_type: str
    required: bool
    on_error: str
    timeout_seconds: float
    state: DetectorState = DetectorState.CONFIGURED
    reason_code: DetectorReasonCode | None = None
    detector: Any | None = None

    @property
    def loaded(self) -> bool:
        """Return whether a live detector instance exists."""
        return self.detector is not None

    @property
    def has_issue(self) -> bool:
        """Return whether this status currently represents degraded safety."""
        return self.state in {DetectorState.UNAVAILABLE, DetectorState.UNHEALTHY}

    @property
    def is_strict(self) -> bool:
        """Return whether an issue must prevent traffic admission."""
        return self.required or self.on_error == "fail_closed"

    def to_public_dict(self) -> dict[str, str]:
        """Return the stable issue fields exposed by readiness."""
        data = {
            "name": self.name,
            "direction": self.direction,
            "state": self.state.value,
        }
        if self.reason_code is not None:
            data["reason_code"] = self.reason_code.value
        return data

    def to_availability_dict(self) -> dict[str, str | bool]:
        """Return the stable request-audit availability contract."""
        return {
            "name": self.name,
            "direction": self.direction,
            "state": self.state.value,
            "required": self.required,
            "on_error": self.on_error,
            "reason_code": self.reason_code.value if self.reason_code else "",
        }


TransitionCallback = Callable[[DetectorStatus, DetectorStatus], None]


class DetectorStatusRegistry:
    """Thread-safe state registry scoped to a single FastAPI application."""

    def __init__(self, on_transition: TransitionCallback | None = None) -> None:
        self._statuses: dict[tuple[DetectorDirection, str], DetectorStatus] = {}
        self._on_transition = on_transition
        self._lock = RLock()

    def register(
        self,
        *,
        direction: DetectorDirection | str,
        name: str,
        detector_type: str,
        required: bool,
        on_error: str,
        timeout_seconds: float,
    ) -> DetectorStatus:
        """Register one configured detector and return its initial snapshot."""
        normalized_direction = self._normalize_direction(direction)
        key = (normalized_direction, name)
        status = DetectorStatus(
            direction=normalized_direction,
            name=name,
            detector_type=detector_type or "builtin",
            required=required,
            on_error=on_error,
            timeout_seconds=timeout_seconds,
        )
        with self._lock:
            if key in self._statuses:
                raise ValueError(
                    f"Detector status already registered: {normalized_direction}/{name}"
                )
            self._statuses[key] = status
        return status

    def get(self, direction: DetectorDirection | str, name: str) -> DetectorStatus:
        """Return the current immutable snapshot for a configured detector."""
        key = (self._normalize_direction(direction), name)
        with self._lock:
            return self._statuses[key]

    def contains(self, direction: DetectorDirection | str, name: str) -> bool:
        """Return whether a configured identity is registered."""
        key = (self._normalize_direction(direction), name)
        with self._lock:
            return key in self._statuses

    def transition(
        self,
        direction: DetectorDirection | str,
        name: str,
        state: DetectorState,
        *,
        reason_code: DetectorReasonCode | None = None,
        detector: Any | None = None,
    ) -> DetectorStatus:
        """Apply an idempotent state transition and notify on actual changes."""
        key = (self._normalize_direction(direction), name)
        with self._lock:
            old = self._statuses[key]
            effective_reason = None if state is DetectorState.HEALTHY else reason_code
            effective_detector = old.detector if detector is None else detector
            new = replace(
                old,
                state=state,
                reason_code=effective_reason,
                detector=effective_detector,
            )
            if new == old:
                return old
            self._statuses[key] = new
        if self._on_transition is not None:
            self._on_transition(old, new)
        return new

    def snapshot(self) -> list[DetectorStatus]:
        """Return a deterministic immutable snapshot of all configured detectors."""
        with self._lock:
            statuses = list(self._statuses.values())
        return sorted(statuses, key=lambda item: (item.direction, item.name))

    def issues(self, *, strict: bool | None = None) -> list[DetectorStatus]:
        """Return deterministic issue snapshots, optionally filtered by policy."""
        issues = [status for status in self.snapshot() if status.has_issue]
        if strict is None:
            return issues
        return [status for status in issues if status.is_strict is strict]

    @staticmethod
    def _normalize_direction(direction: DetectorDirection | str) -> DetectorDirection:
        if direction not in {"input", "output"}:
            raise ValueError(f"Unsupported detector direction: {direction}")
        return direction
