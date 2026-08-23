"""Explicit Flow policy resolution and failure decision tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.flow.policy import (
    AvailabilityPolicyConfig,
    DegradationPolicyConfig,
    FailureKind,
    FailurePolicyConfig,
    NodePolicyConfig,
    PolicyConflictError,
    PolicyDefaults,
    PolicySource,
    StopPolicyConfig,
    TimeoutPolicyConfig,
    effective_timeout_seconds,
    evaluate_failure,
    resolve_node_policy,
    settle_flow_deadline,
)


def test_tc_fp_001() -> None:
    """TC-FP-001: every policy dimension is resolved with a traceable source."""
    explicit = resolve_node_policy(
        NodePolicyConfig(
            timeout=TimeoutPolicyConfig(seconds=7.5, action="fail_closed"),
            failure=FailurePolicyConfig(action="fail_open"),
            availability=AvailabilityPolicyConfig(
                required=False,
                on_unavailable="fail_open",
                on_circuit_open="fail_closed",
            ),
            degradation=DegradationPolicyConfig(
                allowed=True,
                emit_evidence=True,
                emit_metrics=True,
            ),
            stop=StopPolicyConfig(signals=("safety.block",)),
        ),
        defaults=PolicyDefaults(),
        source=PolicySource.EXPLICIT,
    )
    assert explicit.timeout.seconds == 7.5
    assert explicit.failure.action == "fail_open"
    assert explicit.availability.on_circuit_open == "fail_closed"
    assert explicit.degradation.emit_evidence is True
    assert explicit.stop.signals == ("safety.block",)
    assert set(explicit.sources.model_dump().values()) == {"explicit"}

    legacy_defaults = resolve_node_policy(
        NodePolicyConfig(),
        defaults=PolicyDefaults(),
        source=PolicySource.LEGACY,
    )
    assert set(legacy_defaults.sources.model_dump().values()) == {"legacy_default"}


def test_tc_fp_002() -> None:
    """TC-FP-002: ordinary exceptions follow failure policy without raw exceptions."""
    fail_open = resolve_node_policy(
        NodePolicyConfig(failure=FailurePolicyConfig(action="fail_open")),
        defaults=PolicyDefaults(),
    )
    open_decision = evaluate_failure(fail_open, FailureKind.ERROR)
    assert open_decision.action == "fail_open"
    assert open_decision.reason_code == "capability_error"
    assert open_decision.degraded is True
    assert open_decision.stop_requested is False
    assert "exception" not in open_decision.model_dump()

    fail_closed = resolve_node_policy(
        NodePolicyConfig(failure=FailurePolicyConfig(action="fail_closed")),
        defaults=PolicyDefaults(),
    )
    closed_decision = evaluate_failure(fail_closed, FailureKind.ERROR)
    assert closed_decision.action == "fail_closed"
    assert closed_decision.stop_requested is True


def test_tc_fp_003() -> None:
    """TC-FP-003: timeout action is independent from ordinary error action."""
    policy = resolve_node_policy(
        NodePolicyConfig(
            timeout=TimeoutPolicyConfig(seconds=0.05, action="fail_closed"),
            failure=FailurePolicyConfig(action="fail_open"),
        ),
        defaults=PolicyDefaults(),
    )

    timeout_decision = evaluate_failure(policy, FailureKind.TIMEOUT)
    error_decision = evaluate_failure(policy, FailureKind.ERROR)
    assert timeout_decision.action == "fail_closed"
    assert timeout_decision.reason_code == "node_timeout"
    assert error_decision.action == "fail_open"
    assert error_decision.reason_code == "capability_error"


def test_tc_fp_004() -> None:
    """TC-FP-004: unavailable and circuit-open use separate explicit policy."""
    policy = resolve_node_policy(
        NodePolicyConfig(
            availability=AvailabilityPolicyConfig(
                required=False,
                on_unavailable="fail_open",
                on_circuit_open="fail_closed",
            )
        ),
        defaults=PolicyDefaults(),
    )

    unavailable = evaluate_failure(policy, FailureKind.UNAVAILABLE)
    circuit_open = evaluate_failure(policy, FailureKind.CIRCUIT_OPEN)
    assert unavailable.action == "fail_open"
    assert unavailable.reason_code == "capability_unavailable"
    assert unavailable.invocation_allowed is False
    assert circuit_open.action == "fail_closed"
    assert circuit_open.reason_code == "circuit_open"
    assert circuit_open.invocation_allowed is False


def test_tc_fp_005() -> None:
    """TC-FP-005: parent deadline bounds nodes and settles pending policies deterministically."""
    first_policy = resolve_node_policy(
        NodePolicyConfig(timeout=TimeoutPolicyConfig(seconds=5.0, action="fail_open")),
        defaults=PolicyDefaults(),
    )
    second_policy = resolve_node_policy(
        NodePolicyConfig(timeout=TimeoutPolicyConfig(seconds=2.0, action="fail_closed")),
        defaults=PolicyDefaults(),
    )
    completed = {"already-done": "result"}

    settlement = settle_flow_deadline(
        completed=completed,
        pending=(("first", first_policy), ("second", second_policy)),
    )

    assert effective_timeout_seconds(first_policy, flow_remaining_seconds=0.25) == 0.25
    assert settlement.completed == completed
    assert [item.node_id for item in settlement.pending] == ["first", "second"]
    assert [item.decision.action for item in settlement.pending] == [
        "fail_open",
        "fail_closed",
    ]
    assert settlement.flow_status == "timed_out"
    assert settlement.ready_for_reducer is True


def test_tc_fp_006() -> None:
    """TC-FP-006: invalid or contradictory policy is rejected before execution."""
    with pytest.raises(ValidationError):
        TimeoutPolicyConfig(seconds=0, action="fail_open")
    with pytest.raises(ValidationError):
        FailurePolicyConfig(action="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        StopPolicyConfig(signals=())

    with pytest.raises(PolicyConflictError) as required_error:
        resolve_node_policy(
            NodePolicyConfig(
                availability=AvailabilityPolicyConfig(
                    required=True,
                    on_unavailable="fail_open",
                    on_circuit_open="fail_closed",
                )
            ),
            defaults=PolicyDefaults(),
            flow_id="input-flow",
            node_id="required-detector",
        )
    assert required_error.value.code == "policy_conflict"
    assert required_error.value.flow_id == "input-flow"
    assert required_error.value.node_id == "required-detector"

    with pytest.raises(PolicyConflictError):
        resolve_node_policy(
            NodePolicyConfig(
                failure=FailurePolicyConfig(action="fail_open"),
                degradation=DegradationPolicyConfig(allowed=False),
            ),
            defaults=PolicyDefaults(),
        )
