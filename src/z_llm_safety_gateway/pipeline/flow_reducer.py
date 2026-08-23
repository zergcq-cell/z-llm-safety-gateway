"""Detector-domain reducer Capability for the default safety Flow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from z_llm_safety_gateway.circuit_breaker import CircuitBreaker
from z_llm_safety_gateway.flow.contracts import CapabilityDescriptor, FlowDefinition
from z_llm_safety_gateway.flow.evidence import NodeStatus
from z_llm_safety_gateway.flow.runtime import (
    CapabilityResult,
    NodeExecutionResult,
)
from z_llm_safety_gateway.models import DetectionResult, Modification
from z_llm_safety_gateway.pipeline.aggregator import ResultAggregator
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule


class DetectorReductionResult(BaseModel):
    """In-memory detector aggregation consumed by the Pipeline compatibility facade."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    final_action: str = "allow"
    overall_risk_level: str = "low"
    detector_results: tuple[DetectionResult, ...] = ()
    modifications: tuple[Modification, ...] = ()


@dataclass(frozen=True, slots=True)
class DetectorFailureFallback:
    """Legacy failure details needed only by the detector-domain reducer."""

    detector_name: str
    on_error: str
    breaker: CircuitBreaker | None = None
    on_timeout: str | None = None
    on_unavailable: str | None = None
    on_circuit_open: str | None = None

    def action_for(self, reason_code: str) -> str:
        if reason_code == "node_timeout":
            return self.on_timeout or self.on_error
        if reason_code == "capability_unavailable":
            return self.on_unavailable or self.on_error
        if reason_code == "circuit_open":
            if self.on_circuit_open is not None:
                return self.on_circuit_open
            if self.breaker is not None:
                return self.breaker.fallback_action
        return self.on_error


class DetectorResultReducer:
    """Keep detector precedence and modification semantics outside Flow core."""

    descriptor = CapabilityDescriptor(
        contract_version="1.0",
        capability_id="detector-result-reducer",
        implementation_version="1.0.0",
        input_schema="flow.node-results.v1",
        output_schema="safety.detector-result.v1",
        name="detector-result-reducer",
        category="safety-reducer",
    )

    def __init__(
        self,
        *,
        priorities: Mapping[str, int] | None = None,
        message_indices: tuple[int | None, ...] = (),
        flag_escalation: FlagEscalationRule | None = None,
        failure_fallbacks: Mapping[str | tuple[str, str], DetectorFailureFallback] | None = None,
    ) -> None:
        self._priorities = dict(priorities or {})
        self._message_indices = message_indices
        self._aggregator = ResultAggregator(flag_escalation=flag_escalation)
        self._failure_fallbacks = {
            (("*", key) if isinstance(key, str) else key): value
            for key, value in (failure_fallbacks or {}).items()
        }

    async def reduce(
        self,
        flow: FlowDefinition,
        results: tuple[NodeExecutionResult, ...],
    ) -> CapabilityResult:
        detections: list[DetectionResult] = []
        message_indices: list[int | None] = []
        for result in results:
            if result.status in {NodeStatus.SUCCEEDED, NodeStatus.PARTIAL} and isinstance(
                result.output, DetectorReductionResult
            ):
                detections.extend(result.output.detector_results)
                message_indices.extend([None] * len(result.output.detector_results))
                continue
            detection = self._detection_result(flow, result)
            if detection is None:
                continue
            detections.append(detection)
            message_indices.append(
                self._message_indices[result.item_index]
                if result.item_index < len(self._message_indices)
                else None
            )
        aggregated = self._aggregator.aggregate(
            detections,
            priorities=self._priorities,
            message_indices=message_indices,
        )
        reduction = DetectorReductionResult(
            final_action=aggregated.final_action,
            overall_risk_level=aggregated.overall_risk_level,
            detector_results=tuple(detections),
            modifications=tuple(aggregated.modifications),
        )
        return CapabilityResult(
            output=reduction,
            signals=(f"safety.{reduction.final_action}",),
            evidence_summary={
                "action": reduction.final_action,
                "risk_level": reduction.overall_risk_level,
                "match_count": len(detections),
            },
        )

    def _detection_result(
        self,
        flow: FlowDefinition,
        result: NodeExecutionResult,
    ) -> DetectionResult | None:
        if result.status is NodeStatus.SUCCEEDED:
            return result.output if isinstance(result.output, DetectionResult) else None
        if result.status not in {
            NodeStatus.FAILED,
            NodeStatus.TIMED_OUT,
            NodeStatus.SKIPPED,
        }:
            return None
        fallback = self._failure_fallbacks.get(
            (flow.flow_id, result.node_id),
            self._failure_fallbacks.get(("*", result.node_id)),
        )
        if fallback is None:
            return None
        if result.reason_code == "circuit_open":
            on_error = fallback.action_for(result.reason_code)
            reason = f"Circuit breaker open for '{fallback.detector_name}'"
            reason_code = "circuit_open"
        else:
            on_error = fallback.action_for(result.reason_code)
            reason = (
                f"Detector '{fallback.detector_name}' timed out"
                if result.status is NodeStatus.TIMED_OUT
                else f"Detector '{fallback.detector_name}' failed"
            )
            reason_code = result.reason_code
        return _make_failure_result(
            detector_name=fallback.detector_name,
            on_error=on_error,
            reason=reason,
            reason_code=reason_code,
            duration_ms=result.duration_ms,
        )


def _make_failure_result(
    *,
    detector_name: str,
    on_error: str,
    reason: str,
    reason_code: str,
    duration_ms: float,
) -> DetectionResult:
    fail_closed = on_error == "fail_closed"
    strategy = "fail_closed" if fail_closed else "fail_open"
    return DetectionResult(
        detector_name=detector_name,
        category=("circuit_breaker" if reason_code == "circuit_open" else "error"),
        action="block" if fail_closed else "allow",
        confidence=1.0 if fail_closed else 0.0,
        risk_level="high" if fail_closed else "low",
        message=f"Detector '{detector_name}' failed ({strategy}): {reason}",
        error=reason_code,
        duration_ms=duration_ms,
    )
