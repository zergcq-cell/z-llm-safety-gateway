"""Prometheus detector availability metric tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from z_llm_safety_gateway.app import (
    _build_detector_transition_handler,
    _initialize_detectors,
)
from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry
from z_llm_safety_gateway.exceptions import SafetyUnavailableError
from z_llm_safety_gateway.observability import metrics
from z_llm_safety_gateway.routes.chat import _enforce_detector_availability


@pytest.fixture(autouse=True)
def reset_metrics() -> None:
    metrics.set_enabled(False)
    yield
    metrics.set_enabled(False)


def test_initialization_failure_counter_has_bounded_policy_labels() -> None:
    """TC-PROM-601: initialization failure counter uses the locked label set."""
    metrics.set_enabled(True)
    metrics.record_detector_initialization_failure(
        detector_name="guard",
        direction="input",
        detector_type="grpc",
        policy="fail_closed",
    )

    output = metrics.generate_latest().decode()
    assert (
        'safety_detector_initialization_failures_total{detector_name="guard",'
        'detector_type="grpc",direction="input",policy="fail_closed"} 1.0'
    ) in output
    assert "secret-token" not in output


def test_detector_up_gauge_tracks_health_transitions() -> None:
    """TC-PROM-602: up gauge changes between healthy and unavailable/unhealthy."""
    metrics.set_enabled(True)
    metrics.set_detector_up("guard", "output", "builtin", True)
    assert 'safety_detector_up{detector_name="guard"' in metrics.generate_latest().decode()
    assert "} 1.0" in metrics.generate_latest().decode().split("safety_detector_up", 1)[1]

    metrics.set_detector_up("guard", "output", "builtin", False)
    output = metrics.generate_latest().decode()
    sample = next(line for line in output.splitlines() if line.startswith("safety_detector_up{"))
    assert sample.endswith(" 0.0")


def test_detector_up_gauge_is_wired_to_registry_transitions() -> None:
    """TC-PROM-602: lifecycle callback drives the full 1→0→1 gauge sequence."""
    metrics.set_enabled(True)
    audit = SimpleNamespace(record=lambda event: None)
    statuses = DetectorStatusRegistry(
        on_transition=_build_detector_transition_handler(audit)
    )
    statuses.register(
        direction="output",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error="fail_open",
        timeout_seconds=1.0,
    )

    def value() -> str:
        output = metrics.generate_latest().decode()
        return next(
            line for line in output.splitlines() if line.startswith("safety_detector_up{")
        ).rsplit(" ", 1)[-1]

    statuses.transition("output", "guard", DetectorState.HEALTHY, detector=object())
    assert value() == "1.0"
    statuses.transition("output", "guard", DetectorState.UNHEALTHY)
    assert value() == "0.0"
    statuses.transition("output", "guard", DetectorState.HEALTHY)
    assert value() == "1.0"


@pytest.mark.asyncio
async def test_initialization_failure_counter_is_wired_to_coordinator() -> None:
    """TC-PROM-601: real coordinator failure increments the bounded counter."""
    class FailingRegistry:
        async def create_detector(self, name: str, config: dict[str, object]) -> object:
            raise RuntimeError("private-secret")

    metrics.set_enabled(True)
    await _initialize_detectors(
        FailingRegistry(),
        {"guard": {"on_error": "fail_open", "timeout_seconds": 1.0}},
        direction="input",
        status_registry=DetectorStatusRegistry(),
    )

    output = metrics.generate_latest().decode()
    assert (
        'safety_detector_initialization_failures_total{detector_name="guard",'
        'detector_type="in_process",direction="input",policy="fail_open"} 1.0'
    ) in output
    assert "private-secret" not in output


def test_fail_open_guard_counts_each_degraded_detector_once_per_request() -> None:
    """TC-PROM-603: request guard increments each fail-open issue once."""
    metrics.set_enabled(True)
    statuses = DetectorStatusRegistry()
    for direction, name in [("input", "alpha"), ("output", "beta")]:
        statuses.register(
            direction=direction,
            name=name,
            detector_type="builtin",
            required=False,
            on_error="fail_open",
            timeout_seconds=1.0,
        )
        statuses.transition(direction, name, DetectorState.UNAVAILABLE)
    app_state = SimpleNamespace(
        detector_status_registry=statuses,
        input_detectors=[],
        output_detectors=[],
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=app_state),
        state=SimpleNamespace(),
    )

    _enforce_detector_availability(request)

    output = metrics.generate_latest().decode()
    assert (
        'safety_gateway_degraded_requests_total{detector_name="alpha",direction="input"}'
        " 1.0"
    ) in output
    assert (
        'safety_gateway_degraded_requests_total{detector_name="beta",direction="output"}'
        " 1.0"
    ) in output


def test_strict_rejection_does_not_count_as_degraded_continuation() -> None:
    """TC-PROM-603: mixed strict issues do not count a request that is rejected."""
    metrics.set_enabled(True)
    statuses = DetectorStatusRegistry()
    for name, on_error in [("open_guard", "fail_open"), ("closed_guard", "fail_closed")]:
        statuses.register(
            direction="input",
            name=name,
            detector_type="builtin",
            required=False,
            on_error=on_error,
            timeout_seconds=1.0,
        )
        statuses.transition("input", name, DetectorState.UNAVAILABLE)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                detector_status_registry=statuses,
                input_detectors=[],
                output_detectors=[],
            )
        ),
        state=SimpleNamespace(),
    )

    with pytest.raises(SafetyUnavailableError):
        _enforce_detector_availability(request)

    assert "safety_gateway_degraded_requests_total{" not in metrics.generate_latest().decode()


def test_detector_availability_metrics_disabled_are_no_op() -> None:
    """TC-PROM-604: disabled metrics never register or alter decisions."""
    metrics.set_enabled(False)
    metrics.record_detector_initialization_failure("guard", "input", "grpc", "required")
    metrics.set_detector_up("guard", "input", "grpc", False)
    metrics.record_degraded_request("input", "guard")
    assert metrics.generate_latest() == b""

    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error="fail_open",
        timeout_seconds=1.0,
    )
    statuses.transition("input", "guard", DetectorState.UNAVAILABLE)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                detector_status_registry=statuses,
                input_detectors=[],
                output_detectors=[],
            )
        ),
        state=SimpleNamespace(),
    )
    _enforce_detector_availability(request)
    assert request.state.safety_degraded is True
    assert metrics.generate_latest() == b""
