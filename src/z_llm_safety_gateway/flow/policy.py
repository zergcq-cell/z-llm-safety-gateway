"""Explicit, immutable Flow policy resolution and failure decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FallbackAction = Literal["fail_open", "fail_closed"]


class _StrictPolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class PolicySource(str, Enum):
    """Origin of a normalized policy dimension."""

    EXPLICIT = "explicit"
    LEGACY = "legacy"
    LEGACY_DEFAULT = "legacy_default"
    DEFAULT = "default"


class FailureKind(str, Enum):
    """Stable runtime failure classes that select independent policies."""

    ERROR = "error"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    CIRCUIT_OPEN = "circuit_open"


class TimeoutPolicyConfig(_StrictPolicyModel):
    seconds: float = Field(gt=0, le=120)
    action: FallbackAction


class FailurePolicyConfig(_StrictPolicyModel):
    action: FallbackAction


class AvailabilityPolicyConfig(_StrictPolicyModel):
    required: bool = False
    on_unavailable: FallbackAction = "fail_open"
    on_circuit_open: FallbackAction = "fail_open"


class DegradationPolicyConfig(_StrictPolicyModel):
    allowed: bool = True
    emit_evidence: bool = True
    emit_metrics: bool = True


class StopPolicyConfig(_StrictPolicyModel):
    signals: tuple[str, ...] = Field(min_length=1, max_length=32)

    @field_validator("signals")
    @classmethod
    def _validate_signals(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() or len(value) > 128 for value in values):
            raise ValueError("invalid_stop_signal")
        if len(values) != len(set(values)):
            raise ValueError("duplicate_stop_signal")
        return values


class NodePolicyConfig(_StrictPolicyModel):
    """Possibly partial policy supplied by explicit or legacy configuration."""

    timeout: TimeoutPolicyConfig | None = None
    failure: FailurePolicyConfig | None = None
    availability: AvailabilityPolicyConfig | None = None
    degradation: DegradationPolicyConfig | None = None
    stop: StopPolicyConfig | None = None


class PolicyDefaults(_StrictPolicyModel):
    """Documented defaults applied only during startup normalization."""

    timeout: TimeoutPolicyConfig = TimeoutPolicyConfig(seconds=30.0, action="fail_open")
    failure: FailurePolicyConfig = FailurePolicyConfig(action="fail_open")
    availability: AvailabilityPolicyConfig = AvailabilityPolicyConfig()
    degradation: DegradationPolicyConfig = DegradationPolicyConfig()
    stop: StopPolicyConfig = StopPolicyConfig(signals=("safety.block",))


class ResolvedPolicySources(_StrictPolicyModel):
    timeout: PolicySource
    failure: PolicySource
    availability: PolicySource
    degradation: PolicySource
    stop: PolicySource


class ResolvedNodePolicy(_StrictPolicyModel):
    """Complete policy snapshot consumed without runtime default inference."""

    timeout: TimeoutPolicyConfig
    failure: FailurePolicyConfig
    availability: AvailabilityPolicyConfig
    degradation: DegradationPolicyConfig
    stop: StopPolicyConfig
    sources: ResolvedPolicySources


class PolicyDecision(_StrictPolicyModel):
    """Stable result of selecting one failure policy; never contains exceptions."""

    failure_kind: FailureKind
    action: FallbackAction
    reason_code: str
    degraded: bool
    stop_requested: bool
    invocation_allowed: bool


class PolicyConflictError(ValueError):
    """Stable startup diagnostic for contradictory policy."""

    def __init__(
        self,
        *,
        flow_id: str | None = None,
        node_id: str | None = None,
    ) -> None:
        self.code = "policy_conflict"
        self.flow_id = flow_id
        self.node_id = node_id
        parts = [self.code]
        if flow_id is not None:
            parts.append(f"flow_id={flow_id}")
        if node_id is not None:
            parts.append(f"node_id={node_id}")
        super().__init__(": ".join(parts))


def _resolved_source(value: object | None, source: PolicySource) -> PolicySource:
    if value is not None:
        return source
    if source is PolicySource.LEGACY:
        return PolicySource.LEGACY_DEFAULT
    return PolicySource.DEFAULT


def resolve_node_policy(
    config: NodePolicyConfig,
    *,
    defaults: PolicyDefaults,
    source: PolicySource = PolicySource.EXPLICIT,
    flow_id: str | None = None,
    node_id: str | None = None,
) -> ResolvedNodePolicy:
    """Resolve every policy dimension once and reject contradictory choices."""
    timeout = config.timeout or defaults.timeout
    failure = config.failure or defaults.failure
    availability = config.availability or defaults.availability
    degradation = config.degradation or defaults.degradation
    stop = config.stop or defaults.stop

    fallback_actions = {
        timeout.action,
        failure.action,
        availability.on_unavailable,
        availability.on_circuit_open,
    }
    required_fail_open = availability.required and (
        availability.on_unavailable == "fail_open"
        or availability.on_circuit_open == "fail_open"
    )
    hidden_degradation = not degradation.emit_evidence
    forbidden_fail_open = not degradation.allowed and "fail_open" in fallback_actions
    if required_fail_open or hidden_degradation or forbidden_fail_open:
        raise PolicyConflictError(flow_id=flow_id, node_id=node_id)

    return ResolvedNodePolicy(
        timeout=timeout,
        failure=failure,
        availability=availability,
        degradation=degradation,
        stop=stop,
        sources=ResolvedPolicySources(
            timeout=_resolved_source(config.timeout, source),
            failure=_resolved_source(config.failure, source),
            availability=_resolved_source(config.availability, source),
            degradation=_resolved_source(config.degradation, source),
            stop=_resolved_source(config.stop, source),
        ),
    )


_FAILURE_REASONS: dict[FailureKind, str] = {
    FailureKind.ERROR: "capability_error",
    FailureKind.TIMEOUT: "node_timeout",
    FailureKind.UNAVAILABLE: "capability_unavailable",
    FailureKind.CIRCUIT_OPEN: "circuit_open",
}


def evaluate_failure(policy: ResolvedNodePolicy, kind: FailureKind) -> PolicyDecision:
    """Select the configured action for one stable failure class."""
    if kind is FailureKind.ERROR:
        action = policy.failure.action
    elif kind is FailureKind.TIMEOUT:
        action = policy.timeout.action
    elif kind is FailureKind.UNAVAILABLE:
        action = policy.availability.on_unavailable
    else:
        action = policy.availability.on_circuit_open

    return PolicyDecision(
        failure_kind=kind,
        action=action,
        reason_code=_FAILURE_REASONS[kind],
        degraded=True,
        stop_requested=action == "fail_closed",
        invocation_allowed=kind not in {FailureKind.UNAVAILABLE, FailureKind.CIRCUIT_OPEN},
    )


def effective_timeout_seconds(
    policy: ResolvedNodePolicy,
    *,
    flow_remaining_seconds: float,
) -> float:
    """Bound a Node timeout by its parent Flow's remaining deadline."""
    return max(0.0, min(policy.timeout.seconds, flow_remaining_seconds))


@dataclass(frozen=True, slots=True)
class PendingPolicySettlement:
    node_id: str
    decision: PolicyDecision


@dataclass(frozen=True, slots=True)
class DeadlineSettlement:
    completed: Mapping[str, Any]
    pending: tuple[PendingPolicySettlement, ...]
    flow_status: Literal["timed_out"] = "timed_out"
    ready_for_reducer: bool = True


def settle_flow_deadline(
    *,
    completed: Mapping[str, Any],
    pending: tuple[tuple[str, ResolvedNodePolicy], ...],
) -> DeadlineSettlement:
    """Preserve completed results and deterministically settle pending Node timeouts."""
    settlements = tuple(
        PendingPolicySettlement(
            node_id=node_id,
            decision=evaluate_failure(policy, FailureKind.TIMEOUT),
        )
        for node_id, policy in pending
    )
    return DeadlineSettlement(
        completed=MappingProxyType(dict(completed)),
        pending=settlements,
    )
