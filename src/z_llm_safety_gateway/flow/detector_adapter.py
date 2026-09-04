"""Adapter exposing existing Detector implementations as Flow Capabilities."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import structlog

from z_llm_safety_gateway.detectors.status import (
    DetectorDirection,
    DetectorReasonCode,
    DetectorState,
    DetectorStatus,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.flow.contracts import (
    CapabilityDescriptor,
    FlowContext,
    FlowItem,
)
from z_llm_safety_gateway.flow.runtime import CapabilityResult
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

_ACTION_SIGNALS = {
    "allow": "safety.allow",
    "block": "safety.block",
    "flag": "safety.flag",
    "modify": "safety.modify",
}
_INVALID_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9._:-]+")
logger = structlog.get_logger(__name__)


def _capability_id(detector_name: str) -> str:
    normalized = _INVALID_ID_CHARACTERS.sub("-", detector_name).strip("-")
    if not normalized:
        raise ValueError("invalid_detector_capability_id")
    return f"detector.{normalized}"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _confidence_bucket(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.4:
        return "medium"
    return "low"


class DetectorCapabilityAdapter:
    """Invoke a duck-typed Detector without changing its public SDK contract."""

    def __init__(self, detector: Any) -> None:
        self._detector = detector
        name = str(detector.name)
        self.descriptor = CapabilityDescriptor(
            contract_version="1.0",
            capability_id=_capability_id(name),
            implementation_version=str(detector.version),
            input_schema="safety.text.v1",
            output_schema="safety.detector-result.v1",
            name=name,
            category=str(detector.category),
        )

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        """Map one Flow item to the existing Detector context and normalized result."""
        metadata: Mapping[str, Any] = item.metadata
        detection_context = DetectionContext(
            direction=context.direction,
            request_id=context.request_id,
            user_id=_optional_string(metadata.get("user_id")),
            language=_optional_string(metadata.get("language")),
            message_index=_optional_int(metadata.get("message_index")),
            metadata={
                "flow_item_id": item.item_id,
                "correlation_id": context.correlation_id,
            },
        )
        raw_result = await self._detector.detect(item.content, detection_context)
        result = self._normalize_result(raw_result)
        return CapabilityResult(
            output=result,
            signals=(_ACTION_SIGNALS[result.action],),
            evidence_summary={
                "action": result.action,
                "risk_level": result.risk_level,
                "category": result.category,
                "confidence_bucket": _confidence_bucket(result.confidence),
            },
        )

    @staticmethod
    def _normalize_result(result: Any) -> DetectionResult:
        if isinstance(result, DetectionResult):
            return result
        model_dump = getattr(result, "model_dump", None)
        if callable(model_dump):
            return DetectionResult.model_validate(model_dump())
        to_dict = getattr(result, "to_dict", None)
        if callable(to_dict):
            return DetectionResult.model_validate(to_dict())
        return DetectionResult.model_validate(result)


@dataclass(frozen=True, slots=True)
class DetectorCapabilitySnapshot:
    """Immutable application-scoped detector state captured for one request."""

    states: tuple[DetectorStatus, ...]
    _adapters: Mapping[tuple[DetectorDirection, str], DetectorCapabilityAdapter]

    def state(self, direction: DetectorDirection, name: str) -> DetectorStatus:
        return next(
            item for item in self.states if item.direction == direction and item.name == name
        )

    def adapter(
        self,
        direction: DetectorDirection,
        name: str,
    ) -> DetectorCapabilityAdapter:
        return self._adapters[(direction, name)]


@dataclass(frozen=True, slots=True)
class _DetectorRegistration:
    direction: DetectorDirection
    name: str
    detector: Any
    config: Mapping[str, Any]
    timeout_seconds: float


class DetectorCapabilityCoordinator:
    """Coordinate existing Detector lifecycle/status before exposing adapters."""

    def __init__(self, status_registry: DetectorStatusRegistry) -> None:
        self._status_registry = status_registry
        self._registrations: list[_DetectorRegistration] = []
        self._adapters: dict[
            tuple[DetectorDirection, str], DetectorCapabilityAdapter
        ] = {}
        self._initialized: list[Any] = []
        self._initialized_ids: set[int] = set()

    def register(
        self,
        *,
        direction: DetectorDirection,
        detector: Any,
        config: Mapping[str, Any],
        detector_type: str = "builtin",
        required: bool = False,
        on_error: str = "fail_open",
        timeout_seconds: float = 5.0,
    ) -> None:
        """Register one configured direction without initializing the Detector."""
        name = str(detector.name)
        self._status_registry.register(
            direction=direction,
            name=name,
            detector_type=detector_type,
            required=required,
            on_error=on_error,
            timeout_seconds=timeout_seconds,
        )
        self._registrations.append(
            _DetectorRegistration(
                direction=direction,
                name=name,
                detector=detector,
                config=MappingProxyType(dict(config)),
                timeout_seconds=timeout_seconds,
            )
        )

    async def initialize_all(self) -> None:
        """Initialize and health-check each unique Detector instance exactly once."""
        grouped: dict[int, list[_DetectorRegistration]] = {}
        for registration in self._registrations:
            grouped.setdefault(id(registration.detector), []).append(registration)

        for detector_id, registrations in grouped.items():
            if detector_id in self._initialized_ids:
                continue
            detector = registrations[0].detector
            for registration in registrations:
                self._status_registry.transition(
                    registration.direction,
                    registration.name,
                    DetectorState.INITIALIZING,
                )
            try:
                await detector.initialize(dict(registrations[0].config))
            except asyncio.CancelledError:
                await self._safe_bounded_shutdown(
                    detector, registrations[0].timeout_seconds
                )
                raise
            except Exception:
                await self._safe_bounded_shutdown(
                    detector, registrations[0].timeout_seconds
                )
                for registration in registrations:
                    self._status_registry.transition(
                        registration.direction,
                        registration.name,
                        DetectorState.UNAVAILABLE,
                        reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
                    )
                continue

            self._initialized_ids.add(detector_id)
            self._initialized.append(detector)
            adapter = DetectorCapabilityAdapter(detector)
            reason: DetectorReasonCode | None
            try:
                healthy = await asyncio.wait_for(
                    detector.health_check(),
                    timeout=registrations[0].timeout_seconds,
                )
            except asyncio.CancelledError:
                await self._safe_bounded_shutdown(
                    detector, registrations[0].timeout_seconds
                )
                self._initialized.remove(detector)
                self._initialized_ids.remove(detector_id)
                raise
            except asyncio.TimeoutError:
                state = DetectorState.UNHEALTHY
                reason = DetectorReasonCode.HEALTH_CHECK_TIMEOUT
            except Exception:
                state = DetectorState.UNHEALTHY
                reason = DetectorReasonCode.HEALTH_CHECK_ERROR
            else:
                state = DetectorState.HEALTHY if healthy else DetectorState.UNHEALTHY
                reason = None if healthy else DetectorReasonCode.HEALTH_CHECK_FAILED
            for registration in registrations:
                self._status_registry.transition(
                    registration.direction,
                    registration.name,
                    state,
                    reason_code=reason,
                    detector=detector,
                )
                self._adapters[(registration.direction, registration.name)] = adapter

    async def shutdown_all(self) -> None:
        """Shutdown successfully initialized Detector instances once, in reverse order."""
        for detector in reversed(self._initialized):
            registrations = [
                item for item in self._registrations if item.detector is detector
            ]
            timeout = registrations[0].timeout_seconds if registrations else 5.0
            await self._safe_bounded_shutdown(detector, timeout)
        self._initialized.clear()
        self._initialized_ids.clear()

    def snapshot(self) -> DetectorCapabilitySnapshot:
        """Capture immutable statuses and live adapters for one request."""
        return DetectorCapabilitySnapshot(
            states=tuple(self._status_registry.snapshot()),
            _adapters=MappingProxyType(dict(self._adapters)),
        )

    @staticmethod
    async def _bounded_shutdown(detector: Any, timeout_seconds: float) -> None:
        shutdown = getattr(detector, "shutdown", None)
        if callable(shutdown):
            await asyncio.wait_for(shutdown(), timeout=timeout_seconds)

    @classmethod
    async def _safe_bounded_shutdown(
        cls, detector: Any, timeout_seconds: float
    ) -> None:
        try:
            await cls._bounded_shutdown(detector, timeout_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "detector_capability_cleanup_failed",
                detector_name=str(getattr(detector, "name", "unknown")),
                reason_code="cleanup_error",
                error_type=type(exc).__name__,
            )
