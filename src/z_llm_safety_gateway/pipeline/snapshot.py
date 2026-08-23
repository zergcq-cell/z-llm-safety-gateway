"""Immutable request-level detector Flow availability and execution snapshot."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal
from uuid import uuid4

from z_llm_safety_gateway.detectors.status import DetectorStatus
from z_llm_safety_gateway.flow.evidence import (
    FlowEvidence,
    FlowStatus,
    NodeStatus,
    bound_flow_evidence,
    build_node_evidence,
)
from z_llm_safety_gateway.flow.policy import (
    AvailabilityPolicyConfig,
    DegradationPolicyConfig,
    FailurePolicyConfig,
    NodePolicyConfig,
    PolicyDefaults,
    PolicySource,
    ResolvedNodePolicy,
    StopPolicyConfig,
    TimeoutPolicyConfig,
    resolve_node_policy,
)

SnapshotDirection = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class FlowStageSnapshot:
    """One stage view derived only from its parent request snapshot."""

    snapshot_id: str
    direction: SnapshotDirection
    stage: str
    detectors: tuple[Any, ...]
    detector_configs: Mapping[str, Mapping[str, Any]]
    evidence: FlowEvidence


@dataclass(frozen=True, slots=True)
class FlowExecutionSnapshot:
    """Frozen detector availability, instances, and config for one request."""

    snapshot_id: str
    request_id: str
    statuses: tuple[DetectorStatus, ...]
    input_detectors: tuple[Any, ...]
    output_detectors: tuple[Any, ...]
    input_detector_configs: Mapping[str, Mapping[str, Any]]
    output_detector_configs: Mapping[str, Mapping[str, Any]]
    max_evidence_size: int = 256 * 1024
    input_flow_identity: tuple[str, str] | None = None
    output_flow_identity: tuple[str, str] | None = None
    input_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None
    output_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None

    @property
    def degraded(self) -> bool:
        return bool(self.issues)

    @property
    def issues(self) -> tuple[DetectorStatus, ...]:
        return tuple(status for status in self.statuses if status.has_issue)

    @property
    def strict_issues(self) -> tuple[DetectorStatus, ...]:
        return tuple(status for status in self.issues if status.is_strict)

    def status(self, direction: SnapshotDirection, name: str) -> DetectorStatus:
        return next(
            status
            for status in self.statuses
            if status.direction == direction and status.name == name
        )

    def stage(self, direction: SnapshotDirection, stage: str) -> FlowStageSnapshot:
        """Return an immutable stage view and evidence all request-time skips."""
        detectors = (
            self.input_detectors if direction == "input" else self.output_detectors
        )
        configs = (
            self.input_detector_configs
            if direction == "input"
            else self.output_detector_configs
        )
        return FlowStageSnapshot(
            snapshot_id=self.snapshot_id,
            direction=direction,
            stage=stage,
            detectors=detectors,
            detector_configs=configs,
            evidence=self._stage_evidence(direction, stage),
        )

    def _stage_evidence(
        self,
        direction: SnapshotDirection,
        stage: str,
    ) -> FlowEvidence:
        issues = tuple(status for status in self.issues if status.direction == direction)
        identity = (
            self.input_flow_identity
            if direction == "input"
            else self.output_flow_identity
        )
        flow_id, flow_version = identity or (
            f"legacy-{direction}-detector-flow",
            "1.0.0",
        )
        policies = (
            self.input_detector_policies
            if direction == "input"
            else self.output_detector_policies
        ) or {}
        execution_id = f"{self.snapshot_id}:{direction}:{stage}"[:256]
        nodes = tuple(
            build_node_evidence(
                contract_version="1.0",
                flow_id=flow_id,
                flow_version=flow_version,
                execution_id=execution_id,
                node_id=f"{direction}-{status.name}",
                definition_index=index,
                target_id=f"detector.{status.name}",
                target_contract_version="1.0",
                target_implementation_version=str(
                    getattr(status.detector, "version", "unavailable")
                ),
                effective_policy=policies.get(status.name, _status_policy(status)),
                status=NodeStatus.SKIPPED,
                degraded=True,
                reason_code=(
                    status.reason_code.value
                    if status.reason_code is not None
                    else "capability_unavailable"
                ),
                duration_ms=0.0,
                item_count=1,
                succeeded_items=0,
                failed_items=0,
                skipped_items=1,
                cancelled_items=0,
                signals=(),
            )
            for index, status in enumerate(issues)
        )
        strict = any(status.is_strict for status in issues)
        return bound_flow_evidence(FlowEvidence(
            contract_version="1.0",
            execution_id=execution_id,
            flow_id=flow_id,
            flow_version=flow_version,
            direction=direction,
            stage=stage,
            status=(
                FlowStatus.FAILED
                if strict
                else FlowStatus.PARTIAL
                if issues
                else FlowStatus.COMPLETED
            ),
            reason_code="capability_unavailable" if issues else "completed",
            duration_ms=0.0,
            nodes=nodes,
        ), max_evidence_size=self.max_evidence_size)


def capture_flow_execution_snapshot(
    *,
    request_id: str,
    statuses: Iterable[DetectorStatus],
    input_detectors: Iterable[Any],
    output_detectors: Iterable[Any],
    input_detector_configs: Mapping[str, Mapping[str, Any]],
    output_detector_configs: Mapping[str, Mapping[str, Any]],
    max_evidence_size: int = 256 * 1024,
    input_flow_identity: tuple[str, str] | None = None,
    output_flow_identity: tuple[str, str] | None = None,
    input_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None,
    output_detector_policies: Mapping[str, ResolvedNodePolicy] | None = None,
) -> FlowExecutionSnapshot:
    """Capture one deterministic snapshot before admission or Provider selection."""
    frozen_statuses = tuple(
        sorted(statuses, key=lambda status: (status.direction, status.name))
    )
    issue_detector_ids = {
        id(status.detector)
        for status in frozen_statuses
        if status.has_issue and status.detector is not None
    }
    return FlowExecutionSnapshot(
        snapshot_id=f"snapshot-{uuid4().hex}",
        request_id=request_id or "unknown-request",
        statuses=frozen_statuses,
        input_detectors=tuple(
            detector for detector in input_detectors if id(detector) not in issue_detector_ids
        ),
        output_detectors=tuple(
            detector for detector in output_detectors if id(detector) not in issue_detector_ids
        ),
        input_detector_configs=_freeze_configs(input_detector_configs),
        output_detector_configs=_freeze_configs(output_detector_configs),
        max_evidence_size=max_evidence_size,
        input_flow_identity=input_flow_identity,
        output_flow_identity=output_flow_identity,
        input_detector_policies=(
            MappingProxyType(dict(input_detector_policies or {}))
        ),
        output_detector_policies=(
            MappingProxyType(dict(output_detector_policies or {}))
        ),
    )


def _freeze_configs(
    configs: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    return MappingProxyType(
        {
            name: MappingProxyType(dict(config))
            for name, config in sorted(configs.items())
        }
    )


def _status_policy(status: DetectorStatus) -> Any:
    action: Literal["fail_open", "fail_closed"] = (
        "fail_closed" if status.on_error == "fail_closed" else "fail_open"
    )
    availability_action: Literal["fail_open", "fail_closed"] = (
        "fail_closed" if status.is_strict else "fail_open"
    )
    timeout = max(0.001, min(float(status.timeout_seconds), 120.0))
    return resolve_node_policy(
        NodePolicyConfig(
            timeout=TimeoutPolicyConfig(seconds=timeout, action=action),
            failure=FailurePolicyConfig(action=action),
            availability=AvailabilityPolicyConfig(
                required=status.required,
                on_unavailable=availability_action,
                on_circuit_open=availability_action,
            ),
            degradation=DegradationPolicyConfig(
                allowed=True,
                emit_evidence=True,
                emit_metrics=True,
            ),
            stop=StopPolicyConfig(signals=("safety.block",)),
        ),
        defaults=PolicyDefaults(),
        source=PolicySource.LEGACY,
    )
