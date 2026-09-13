"""Backward-compatible PipelineEngine facade over the default detector Flow."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import structlog
from pydantic import BaseModel, Field

from z_llm_safety_gateway.circuit_breaker import CircuitBreaker
from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.flow.contracts import (
    CapabilityDescriptor,
    CapabilityNodeDefinition,
    FlowContext,
    FlowContractRegistry,
    FlowDefinition,
    FlowInput,
    FlowItem,
)
from z_llm_safety_gateway.flow.evidence import FlowEvidence, SafeEvidenceSummary
from z_llm_safety_gateway.flow.policy import (
    AvailabilityPolicyConfig,
    DegradationPolicyConfig,
    FailureKind,
    FailurePolicyConfig,
    FallbackAction,
    NodePolicyConfig,
    PolicyDefaults,
    PolicySource,
    ResolvedNodePolicy,
    StopPolicyConfig,
    TimeoutPolicyConfig,
    resolve_node_policy,
)
from z_llm_safety_gateway.flow.runtime import (
    CapabilityInvocationError,
    CapabilityResult,
    FlowRuntime,
    OrderedResultReducer,
)
from z_llm_safety_gateway.models import DetectionContext, DetectionResult, Modification
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule
from z_llm_safety_gateway.pipeline.flow_reducer import (
    DetectorFailureFallback,
    DetectorReductionResult,
    DetectorResultReducer,
)
from z_llm_safety_gateway.pipeline.threshold import ThresholdDecisionEngine

logger = structlog.get_logger(__name__)

_DEFAULT_PRIORITY = 100
_DEFAULT_ON_ERROR = "fail_open"
_DEFAULT_BLOCK_THRESHOLD = 1.0
_DEFAULT_FLAG_THRESHOLD = 1.0
_MAX_PIPELINE_TIMEOUT_SECONDS = 120.0
_INVALID_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9._:-]+")
class PipelineResult(BaseModel):
    """The public legacy outcome returned by :meth:`PipelineEngine.run`."""

    final_action: str = "allow"
    overall_risk_level: str = "low"
    detector_results: list[DetectionResult] = Field(default_factory=list)
    modifications: list[Modification] = Field(default_factory=list)
    pipeline_duration_ms: float = 0.0
    flow_evidence: FlowEvidence | None = None


@dataclass(frozen=True, slots=True)
class _PipelinePlan:
    flow: FlowDefinition
    registry: FlowContractRegistry
    capabilities: Mapping[str, _PipelineDetectorCapability]
    policies: Mapping[tuple[str, str, str], ResolvedNodePolicy]
    fallbacks: Mapping[str | tuple[str, str], DetectorFailureFallback]
    priorities: Mapping[str, int]
    runtime: FlowRuntime


@dataclass(frozen=True, slots=True)
class _PipelinePlanCache:
    direction: str
    detectors: tuple[Detector, ...]
    detector_names: tuple[str, ...]
    config_snapshot: dict[str, dict[str, Any]]
    plan: _PipelinePlan


class _PipelineDetectorCapability:
    """Detector-domain adapter retaining the established Pipeline semantics."""

    def __init__(
        self,
        *,
        capability_id: str,
        detector: Detector,
        config: Mapping[str, Any],
    ) -> None:
        self._detector = detector
        self._config = dict(config)
        self._summary_cache: dict[tuple[str, str, str], SafeEvidenceSummary] = {}
        self.descriptor = CapabilityDescriptor(
            contract_version="1.0",
            capability_id=capability_id,
            implementation_version=str(detector.version),
            input_schema="safety.text.v1",
            output_schema="safety.detector-result.v1",
            name=str(detector.name),
            category=str(detector.category),
        )

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        detection_context = item.metadata.get("pipeline_detection_context")
        if not isinstance(detection_context, DetectionContext):
            detection_context = DetectionContext(
                direction=context.direction,
                request_id=context.request_id,
                metadata={},
            )

        detector_name = str(self._detector.name)
        breaker = self._breaker()
        if breaker is not None and not breaker.before_call():
            fallback = breaker.fallback_action
            logger.warning(
                "circuit_breaker_open_skipped",
                detector=detector_name,
                fallback_action=fallback,
            )
            raise CapabilityInvocationError(FailureKind.CIRCUIT_OPEN)

        started = time.monotonic()
        try:
            result = await self._detector.detect(item.content, detection_context)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            duration_ms = (time.monotonic() - started) * 1000.0
            if breaker is not None:
                breaker.record_failure()
            logger.error(
                "detector_error",
                detector=detector_name,
                reason_code="capability_error",
                error_type=type(exc).__name__,
                duration_ms=duration_ms,
            )
            raise CapabilityInvocationError(FailureKind.ERROR) from exc

        duration_ms = (time.monotonic() - started) * 1000.0
        result.duration_ms = duration_ms
        if result.modified_content is not None:
            result.action = "modify"
        else:
            result.action = ThresholdDecisionEngine.decide(
                result.confidence,
                float(self._config.get("block_threshold", _DEFAULT_BLOCK_THRESHOLD)),
                float(self._config.get("flag_threshold", _DEFAULT_FLAG_THRESHOLD)),
            )
        if breaker is not None:
            breaker.record_success()
        return _capability_result(result, self._summary_for(result))

    def _summary_for(self, result: DetectionResult) -> SafeEvidenceSummary:
        key = (result.action, result.risk_level, result.category)
        cached = self._summary_cache.get(key)
        if cached is not None:
            return cached
        summary = SafeEvidenceSummary(
            action=result.action,
            risk_level=result.risk_level,
            category=result.category,
        )
        self._summary_cache[key] = summary
        return summary

    def _breaker(self) -> CircuitBreaker | None:
        value = self._config.get("circuit_breaker")
        return value if isinstance(value, CircuitBreaker) else None

    def _on_error(self) -> str:
        value = self._config.get("on_error", _DEFAULT_ON_ERROR)
        return value if isinstance(value, str) else _DEFAULT_ON_ERROR


class PipelineEngine:
    """Preserve the Detector SDK facade while delegating scheduling to FlowRuntime."""

    def __init__(
        self,
        short_circuit_on: str = "block",
        flag_escalation: FlagEscalationRule | None = None,
        *,
        flows: tuple[FlowDefinition, ...] = (),
        input_flow: tuple[str, str] | None = None,
        output_flow: tuple[str, str] | None = None,
        resolved_policies: Mapping[
            tuple[str, str, str], ResolvedNodePolicy
        ] | None = None,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> None:
        if short_circuit_on not in ("block", "block_and_modify"):
            raise ValueError(
                f"short_circuit_on must be 'block' or 'block_and_modify', "
                f"got '{short_circuit_on}'"
            )
        self._short_circuit_on = short_circuit_on
        self._flag_escalation = flag_escalation
        self._configured_flows = tuple(flows)
        self._stage_flows = {"input": input_flow, "output": output_flow}
        self._configured_policies = dict(resolved_policies or {})
        self._runtime_options = dict(runtime_options or {})
        self._cached_plan: _PipelinePlanCache | None = None
        self._last_pending_flow_tasks = 0

    @property
    def pending_flow_task_count(self) -> int:
        """Return pending tasks from the most recently completed Flow execution."""
        return self._last_pending_flow_tasks

    async def run(
        self,
        detectors: list[Detector],
        contexts: list[DetectionContext],
        detector_configs: dict[str, dict[str, Any]],
        *,
        tenant_observation_context: Any | None = None,
    ) -> PipelineResult:
        """Execute the compatibility Flow once and return the legacy result model."""
        started = time.monotonic()
        if not contexts or (not detectors and not self._configured_flows):
            return PipelineResult(
                pipeline_duration_ms=(time.monotonic() - started) * 1000.0,
            )

        plan = self._plan_for(
            detectors,
            detector_configs,
            direction=contexts[0].direction,
        )
        message_indices = tuple(context.message_index for context in contexts)
        reducer = DetectorResultReducer(
            priorities=plan.priorities,
            message_indices=message_indices,
            flag_escalation=self._flag_escalation,
            failure_fallbacks=plan.fallbacks,
        )
        execution = await plan.runtime.execute(
            plan.flow,
            self._flow_input(contexts, tenant_observation_context),
            reducer=reducer,
        )
        self._last_pending_flow_tasks = plan.runtime.pending_task_count
        reduced = execution.output
        if not isinstance(reduced, DetectorReductionResult):
            raise RuntimeError("detector_reducer_contract_violation")
        return PipelineResult(
            final_action=reduced.final_action,
            overall_risk_level=reduced.overall_risk_level,
            detector_results=list(reduced.detector_results),
            modifications=list(reduced.modifications),
            pipeline_duration_ms=(time.monotonic() - started) * 1000.0,
            flow_evidence=execution.evidence,
        )

    def _plan_for(
        self,
        detectors: list[Detector],
        detector_configs: dict[str, dict[str, Any]],
        *,
        direction: str,
    ) -> _PipelinePlan:
        cached = self._cached_plan
        if (
            cached is not None
            and cached.direction == direction
            and _plan_cache_matches(cached, detectors, detector_configs)
        ):
            return cached.plan
        if self._configured_flows:
            configured = self._build_configured_flow(
                detectors,
                detector_configs,
                direction=direction,
            )
            flow, registry, capabilities, policies = configured[:4]
            fallbacks = cast(
                dict[str | tuple[str, str], DetectorFailureFallback],
                dict(configured[4]),
            )
        else:
            legacy = self._build_flow(
                detectors,
                detector_configs,
            )
            flow, registry, capabilities, policies = legacy[:4]
            fallbacks = cast(
                dict[str | tuple[str, str], DetectorFailureFallback],
                dict(legacy[4]),
            )
        priorities = {
            str(detector.name): int(
                detector_configs.get(str(detector.name), {}).get(
                    "priority", _DEFAULT_PRIORITY
                )
            )
            for detector in detectors
        }
        plan = _PipelinePlan(
            flow=flow,
            registry=registry,
            capabilities=capabilities,
            policies=policies,
            fallbacks=fallbacks,
            priorities=priorities,
            runtime=FlowRuntime(
                registry=registry,
                capabilities=capabilities,
                policies=policies,
                reducer=OrderedResultReducer(),
                max_concurrency=int(
                    self._runtime_options.get("max_concurrency", 64)
                ),
                absolute_timeout=float(
                    self._runtime_options.get(
                        "absolute_timeout", _MAX_PIPELINE_TIMEOUT_SECONDS
                    )
                ),
                max_evidence_size=int(
                    self._runtime_options.get("max_evidence_size", 256 * 1024)
                ),
            ),
        )
        self._cached_plan = _PipelinePlanCache(
            direction=direction,
            detectors=tuple(detectors),
            detector_names=tuple(str(detector.name) for detector in detectors),
            config_snapshot={name: dict(config) for name, config in detector_configs.items()},
            plan=plan,
        )
        return plan

    def _build_configured_flow(
        self,
        detectors: list[Detector],
        detector_configs: Mapping[str, Mapping[str, Any]],
        *,
        direction: str,
    ) -> tuple[
        FlowDefinition,
        FlowContractRegistry,
        dict[str, _PipelineDetectorCapability],
        dict[tuple[str, str, str], ResolvedNodePolicy],
        dict[str | tuple[str, str], DetectorFailureFallback],
    ]:
        reference = self._stage_flows.get(direction)
        if reference is None:
            raise RuntimeError(f"configured_stage_flow_missing: direction={direction}")

        flow_index = {
            (candidate.flow_id, candidate.version): candidate
            for candidate in self._configured_flows
        }
        try:
            selected_flow = flow_index[reference]
        except KeyError as exc:  # validated by GatewayConfig; defensive here
            raise RuntimeError("configured_stage_flow_missing") from exc

        detector_by_capability = {
            f"detector.{detector.name}": detector for detector in detectors
        }
        descriptor_by_id: dict[str, CapabilityDescriptor] = {}
        node_by_capability: dict[str, CapabilityNodeDefinition] = {}
        for candidate in self._configured_flows:
            for node in candidate.nodes:
                if not isinstance(node, CapabilityNodeDefinition):
                    continue
                node_by_capability.setdefault(node.capability_id, node)
                descriptor_by_id.setdefault(
                    node.capability_id,
                    CapabilityDescriptor(
                        contract_version="1.0",
                        capability_id=node.capability_id,
                        implementation_version="unavailable",
                        input_schema=node.input_schema,
                        output_schema=node.output_schema,
                    ),
                )

        capabilities: dict[str, _PipelineDetectorCapability] = {}
        for capability_id, detector in detector_by_capability.items():
            capability_node = node_by_capability.get(capability_id)
            if capability_node is None:
                continue
            detector_name = str(detector.name)
            capability = _PipelineDetectorCapability(
                capability_id=capability_id,
                detector=detector,
                config=detector_configs.get(detector_name, {}),
            )
            capabilities[capability_id] = capability
            descriptor_by_id[capability_id] = capability.descriptor

        registry = FlowContractRegistry(
            capabilities=tuple(descriptor_by_id.values()),
            flows=self._configured_flows,
            max_depth=int(self._runtime_options.get("max_depth", 8)),
            max_nodes=int(self._runtime_options.get("max_nodes", 256)),
        )
        fallbacks: dict[str | tuple[str, str], DetectorFailureFallback] = {}
        for candidate in self._configured_flows:
            for node in candidate.nodes:
                if not isinstance(node, CapabilityNodeDefinition):
                    continue
                policy = self._configured_policies[
                    (candidate.flow_id, candidate.version, node.node_id)
                ]
                detector_name = node.capability_id.removeprefix("detector.")
                config = detector_configs.get(detector_name, {})
                breaker = config.get("circuit_breaker")
                fallbacks[(candidate.flow_id, node.node_id)] = DetectorFailureFallback(
                    detector_name=detector_name,
                    on_error=policy.failure.action,
                    breaker=breaker if isinstance(breaker, CircuitBreaker) else None,
                    on_timeout=policy.timeout.action,
                    on_unavailable=policy.availability.on_unavailable,
                    on_circuit_open=policy.availability.on_circuit_open,
                )
        return (
            selected_flow,
            registry,
            capabilities,
            dict(self._configured_policies),
            fallbacks,
        )

    def _build_flow(
        self,
        detectors: list[Detector],
        detector_configs: Mapping[str, Mapping[str, Any]],
    ) -> tuple[
        FlowDefinition,
        FlowContractRegistry,
        dict[str, _PipelineDetectorCapability],
        dict[tuple[str, str, str], ResolvedNodePolicy],
        dict[str, DetectorFailureFallback],
    ]:
        flow_id = "pipeline-compat-flow"
        flow_version = "1.0.0"
        nodes: list[CapabilityNodeDefinition] = []
        capabilities: dict[str, _PipelineDetectorCapability] = {}
        policies: dict[tuple[str, str, str], ResolvedNodePolicy] = {}
        fallbacks: dict[str, DetectorFailureFallback] = {}
        for index, detector in enumerate(detectors):
            detector_name = str(detector.name)
            safe_name = _safe_contract_component(detector_name)
            capability_id = f"pipeline.detector.{index}.{safe_name}"
            node_id = f"detector-{index}-{safe_name}"
            config = dict(detector_configs.get(detector_name, {}))
            capability = _PipelineDetectorCapability(
                capability_id=capability_id,
                detector=detector,
                config=config,
            )
            timeout_seconds = _timeout_seconds(config)
            on_error = _on_error(config)
            breaker = config.get("circuit_breaker")
            circuit_action: FallbackAction = (
                "fail_closed"
                if isinstance(breaker, CircuitBreaker)
                and breaker.fallback_action == "fail_closed"
                else on_error
            )
            policy = resolve_node_policy(
                NodePolicyConfig(
                    timeout=TimeoutPolicyConfig(
                        seconds=timeout_seconds,
                        action=on_error,
                    ),
                    failure=FailurePolicyConfig(action=on_error),
                    availability=AvailabilityPolicyConfig(
                        on_unavailable=on_error,
                        on_circuit_open=circuit_action,
                    ),
                    degradation=DegradationPolicyConfig(
                        allowed=True,
                        emit_evidence=True,
                        emit_metrics=True,
                    ),
                    stop=StopPolicyConfig(signals=self._stop_signals()),
                ),
                defaults=PolicyDefaults(),
                source=PolicySource.LEGACY,
                flow_id=flow_id,
                node_id=node_id,
            )
            nodes.append(
                CapabilityNodeDefinition(
                    contract_version="1.0",
                    node_id=node_id,
                    capability_id=capability_id,
                    input_schema="safety.text.v1",
                    output_schema="safety.detector-result.v1",
                    priority=int(config.get("priority", _DEFAULT_PRIORITY)),
                    policy=policy.model_dump(mode="json"),
                )
            )
            capabilities[capability_id] = capability
            policies[(flow_id, flow_version, node_id)] = policy
            fallbacks[node_id] = DetectorFailureFallback(
                detector_name=detector_name,
                on_error=on_error,
                breaker=breaker if isinstance(breaker, CircuitBreaker) else None,
            )

        flow = FlowDefinition(
            contract_version="1.0",
            flow_id=flow_id,
            version=flow_version,
            input_schema="safety.text.v1",
            output_schema="safety.detector-result.v1",
            nodes=tuple(nodes),
            reducer_capability_id=DetectorResultReducer.descriptor.capability_id,
        )
        registry = FlowContractRegistry(
            capabilities=tuple(capability.descriptor for capability in capabilities.values()),
            flows=(flow,),
        )
        return flow, registry, capabilities, policies, fallbacks

    def _stop_signals(self) -> tuple[str, ...]:
        if self._short_circuit_on == "block_and_modify":
            return ("safety.block", "safety.modify")
        return ("safety.block",)

    @staticmethod
    def _flow_input(
        contexts: list[DetectionContext], tenant_observation_context: Any | None = None
    ) -> FlowInput:
        first = contexts[0]
        return FlowInput(
            contract_version="1.0",
            items=tuple(
                FlowItem(
                    item_id=f"context-{index}",
                    content=str(context.metadata.get("content", "")),
                    metadata={"pipeline_detection_context": context},
                )
                for index, context in enumerate(contexts)
            ),
            context=FlowContext(
                request_id=first.request_id,
                correlation_id=first.request_id,
                direction=first.direction,
                stage="pipeline-compat",
                tenant_observation_context=tenant_observation_context,
            ),
        )

    _make_error_result = staticmethod(
        lambda detector_name, on_error, error_msg, duration_ms: _make_error_result(
            detector_name=detector_name,
            on_error=on_error,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )
    )
    _make_fallback_result = staticmethod(
        lambda detector_name, fallback_action, reason: _make_fallback_result(
            detector_name=detector_name,
            fallback_action=fallback_action,
            reason=reason,
        )
    )


def _safe_contract_component(value: str) -> str:
    normalized = _INVALID_ID_CHARACTERS.sub("-", value).strip("-")
    return normalized[:80] or "unnamed"


def _plan_cache_matches(
    cached: _PipelinePlanCache,
    detectors: list[Detector],
    detector_configs: Mapping[str, Mapping[str, Any]],
) -> bool:
    if (
        detector_configs != cached.config_snapshot
        or len(detectors) != len(cached.detectors)
    ):
        return False
    for index, detector in enumerate(detectors):
        if detector is not cached.detectors[index]:
            return False
        name = str(detector.name)
        if name != cached.detector_names[index]:
            return False
    return True


def _timeout_seconds(config: Mapping[str, Any]) -> float:
    value = config.get("timeout_seconds")
    if value is None:
        return _MAX_PIPELINE_TIMEOUT_SECONDS
    return max(0.001, min(float(value), _MAX_PIPELINE_TIMEOUT_SECONDS))


def _on_error(config: Mapping[str, Any]) -> FallbackAction:
    value = config.get("on_error", _DEFAULT_ON_ERROR)
    return "fail_closed" if value == "fail_closed" else "fail_open"


def _capability_result(
    result: DetectionResult,
    evidence_summary: SafeEvidenceSummary | None = None,
) -> CapabilityResult:
    return CapabilityResult(
        output=result,
        signals=(f"safety.{result.action}",),
        evidence_summary=evidence_summary
        or {
            "action": result.action,
            "risk_level": result.risk_level,
            "category": result.category,
        },
    )


def _make_error_result(
    *,
    detector_name: str,
    on_error: str,
    error_msg: str,
    duration_ms: float,
) -> DetectionResult:
    fail_closed = on_error == "fail_closed"
    strategy = "fail_closed" if fail_closed else "fail_open"
    return DetectionResult(
        detector_name=detector_name,
        category="error",
        action="block" if fail_closed else "allow",
        confidence=1.0 if fail_closed else 0.0,
        risk_level="high" if fail_closed else "low",
        message=f"Detector '{detector_name}' failed ({strategy}): capability_error",
        error="capability_error",
        duration_ms=duration_ms,
    )


def _make_fallback_result(
    *,
    detector_name: str,
    fallback_action: str,
    reason: str,
) -> DetectionResult:
    fail_closed = fallback_action == "fail_closed"
    strategy = "fail_closed" if fail_closed else "fail_open"
    return DetectionResult(
        detector_name=detector_name,
        category="circuit_breaker",
        action="block" if fail_closed else "allow",
        confidence=1.0 if fail_closed else 0.0,
        risk_level="high" if fail_closed else "low",
        message=(
            f"Circuit breaker open for '{detector_name}' ({strategy}): {reason}"
        ),
        error=reason,
    )
