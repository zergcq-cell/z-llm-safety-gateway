"""Detector lifecycle status tests for the readiness fail-safe change."""

from __future__ import annotations

import json

from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatusRegistry,
)


def _register(
    registry: DetectorStatusRegistry,
    *,
    direction: str = "input",
    name: str = "prompt_injection",
) -> None:
    registry.register(
        direction=direction,
        name=name,
        detector_type="builtin",
        required=False,
        on_error="fail_open",
        timeout_seconds=1.0,
    )


def test_registry_same_name_different_direction_remains_distinct() -> None:
    """TC-DLS-001: direction is part of a detector's configured identity."""
    registry = DetectorStatusRegistry()
    _register(registry, direction="input")
    _register(registry, direction="output")

    assert registry.get("input", "prompt_injection").direction == "input"
    assert registry.get("output", "prompt_injection").direction == "output"
    assert len(registry.snapshot()) == 2


def test_registry_successful_initialization_emits_only_state_changes() -> None:
    """TC-DLS-002: successful initialization follows the locked state machine."""
    events: list[tuple[DetectorState, DetectorState]] = []
    registry = DetectorStatusRegistry(
        on_transition=lambda old, new: events.append((old.state, new.state))
    )
    _register(registry)

    registry.transition("input", "prompt_injection", DetectorState.INITIALIZING)
    registry.transition("input", "prompt_injection", DetectorState.HEALTHY)
    registry.transition("input", "prompt_injection", DetectorState.HEALTHY)

    assert registry.get("input", "prompt_injection").state is DetectorState.HEALTHY
    assert events == [
        (DetectorState.CONFIGURED, DetectorState.INITIALIZING),
        (DetectorState.INITIALIZING, DetectorState.HEALTHY),
    ]


def test_registry_initialization_failure_is_unavailable_and_sanitized() -> None:
    """TC-DLS-003: initialization failures expose only stable reason codes."""
    registry = DetectorStatusRegistry()
    _register(registry)
    registry.transition("input", "prompt_injection", DetectorState.INITIALIZING)
    registry.transition(
        "input",
        "prompt_injection",
        DetectorState.UNAVAILABLE,
        reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
    )

    record = registry.get("input", "prompt_injection")
    serialized = json.dumps(record.to_public_dict())
    assert record.state is DetectorState.UNAVAILABLE
    assert record.reason_code is DetectorReasonCode.INITIALIZATION_ERROR
    assert "secret-token" not in serialized


def test_registry_loaded_detector_can_become_unhealthy_and_recover() -> None:
    """TC-DLS-004: loaded detector health state is recoverable."""
    registry = DetectorStatusRegistry()
    _register(registry)
    registry.transition("input", "prompt_injection", DetectorState.INITIALIZING)
    registry.transition("input", "prompt_injection", DetectorState.HEALTHY)
    registry.transition(
        "input",
        "prompt_injection",
        DetectorState.UNHEALTHY,
        reason_code=DetectorReasonCode.HEALTH_CHECK_ERROR,
    )
    assert registry.get("input", "prompt_injection").state is DetectorState.UNHEALTHY

    registry.transition("input", "prompt_injection", DetectorState.HEALTHY)
    recovered = registry.get("input", "prompt_injection")
    assert recovered.state is DetectorState.HEALTHY
    assert recovered.reason_code is None
