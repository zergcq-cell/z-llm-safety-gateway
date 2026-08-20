"""Detector-aware readiness endpoint tests."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.detectors.status import (
    DetectorState,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.routes.health import router


class HealthDetector:
    def __init__(self, results: list[bool | BaseException], *, delay: float = 0.0) -> None:
        self.results = results
        self.delay = delay
        self.calls = 0

    async def health_check(self) -> bool:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, BaseException):
            raise result
        return result


def _app_with_statuses(
    statuses: DetectorStatusRegistry | None = None,
    *,
    ready: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.state.ready = ready
    if statuses is not None:
        app.state.detector_status_registry = statuses
    app.include_router(router)
    return app


def _loaded_status(
    *,
    on_error: str,
    detector: Any,
    timeout_seconds: float = 0.1,
) -> DetectorStatusRegistry:
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error=on_error,
        timeout_seconds=timeout_seconds,
    )
    statuses.transition("input", "guard", DetectorState.INITIALIZING)
    statuses.transition("input", "guard", DetectorState.HEALTHY, detector=detector)
    return statuses


def test_health_and_ready_are_app_scoped_with_no_detectors() -> None:
    """TC-HEALTH-601: liveness stays pure and readiness does not leak across apps."""
    ready_app = _app_with_statuses(DetectorStatusRegistry(), ready=True)
    not_ready_app = _app_with_statuses(None, ready=False)

    with TestClient(ready_app) as ready_client, TestClient(not_ready_app) as other_client:
        assert ready_client.get("/health").json() == {"status": "healthy"}
        ready_response = ready_client.get("/ready")
        other_response = other_client.get("/ready")

    assert ready_response.status_code == 200
    assert ready_response.json()["status"] == "ready"
    assert ready_response.json()["detectors"]["configured"] == 0
    assert other_response.status_code == 503


def test_ready_strict_issue_returns_not_ready_summary() -> None:
    """TC-HEALTH-602: fail-closed availability issue returns deterministic 503."""
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="output",
        name="guard",
        detector_type="grpc",
        required=False,
        on_error="fail_closed",
        timeout_seconds=0.1,
    )
    statuses.transition("output", "guard", DetectorState.UNAVAILABLE)

    response = TestClient(_app_with_statuses(statuses)).get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "degraded": False,
        "detectors": {
            "configured": 1,
            "loaded": 0,
            "healthy": 0,
            "unavailable": 1,
            "unhealthy": 0,
            "degraded": 0,
            "issues": [
                {
                    "name": "guard",
                    "direction": "output",
                    "state": "unavailable",
                }
            ],
        },
    }


def test_ready_fail_open_issue_returns_exact_degraded_schema() -> None:
    """TC-HEALTH-603: fail-open issue is ready with explicit degraded schema."""
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="toxicity",
        detector_type="ml",
        required=False,
        on_error="fail_open",
        timeout_seconds=0.1,
    )
    statuses.transition("input", "toxicity", DetectorState.UNAVAILABLE)

    response = TestClient(_app_with_statuses(statuses)).get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["degraded"] is True
    assert body["detectors"] == {
        "configured": 1,
        "loaded": 0,
        "healthy": 0,
        "unavailable": 1,
        "unhealthy": 0,
        "degraded": 1,
        "issues": [
            {"name": "toxicity", "direction": "input", "state": "unavailable"}
        ],
    }


def test_ready_health_exception_and_timeout_use_stable_reasons() -> None:
    """TC-HEALTH-604: health exceptions and timeouts are bounded and sanitized."""
    error_status = _loaded_status(
        on_error="fail_open",
        detector=HealthDetector([RuntimeError("secret-token")]),
    )
    timeout_status = _loaded_status(
        on_error="fail_open",
        detector=HealthDetector([True], delay=0.1),
        timeout_seconds=0.001,
    )

    error_response = TestClient(_app_with_statuses(error_status)).get("/ready")
    timeout_response = TestClient(_app_with_statuses(timeout_status)).get("/ready")

    assert error_response.json()["detectors"]["issues"][0]["reason_code"] == (
        "health_check_error"
    )
    assert timeout_response.json()["detectors"]["issues"][0]["reason_code"] == (
        "health_check_timeout"
    )
    assert "secret-token" not in error_response.text


def test_ready_health_recovery_restores_status() -> None:
    """TC-HEALTH-605: a loaded unhealthy detector recovers on a later probe."""
    detector = HealthDetector([False, True])
    statuses = _loaded_status(on_error="fail_closed", detector=detector)
    app = _app_with_statuses(statuses)

    first = TestClient(app).get("/ready")
    second = TestClient(app).get("/ready")

    assert first.status_code == 503
    assert second.status_code == 200
    assert statuses.get("input", "guard").state is DetectorState.HEALTHY


def test_ready_keeps_duck_typed_plugin_without_health_check_healthy() -> None:
    """A valid in-process plugin may rely on the optional health default."""
    plugin = object()
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="plugin_guard",
        detector_type="in_process",
        required=False,
        on_error="fail_closed",
        timeout_seconds=0.1,
    )
    statuses.transition(
        "input", "plugin_guard", DetectorState.HEALTHY, detector=plugin
    )

    response = TestClient(_app_with_statuses(statuses)).get("/ready")

    assert response.status_code == 200
    assert response.json()["degraded"] is False
    assert statuses.get("input", "plugin_guard").state is DetectorState.HEALTHY


def test_ready_checks_loaded_detectors_concurrently() -> None:
    """TC-HEALTH-604: health probe latency is bounded by the slowest detector."""
    started = 0
    both_started = asyncio.Event()

    class CoordinatedDetector:
        async def health_check(self) -> bool:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await both_started.wait()
            return True

    statuses = DetectorStatusRegistry()
    for name in ("alpha", "beta"):
        statuses.register(
            direction="input",
            name=name,
            detector_type="builtin",
            required=False,
            on_error="fail_open",
            timeout_seconds=0.05,
        )
        statuses.transition(
            "input", name, DetectorState.HEALTHY, detector=CoordinatedDetector()
        )

    response = TestClient(_app_with_statuses(statuses)).get("/ready")

    assert response.status_code == 200
    assert started == 2
    assert response.json()["degraded"] is False
    assert response.json()["detectors"]["healthy"] == 2
    assert response.json()["detectors"]["unhealthy"] == 0


def test_ready_recovery_emits_one_state_transition() -> None:
    """TC-HEALTH-605: recovery transition is emitted once, not on every probe."""
    transitions: list[tuple[str, str]] = []
    statuses = DetectorStatusRegistry(
        on_transition=lambda old, new: transitions.append(
            (old.state.value, new.state.value)
        )
    )
    detector = HealthDetector([False, True, True])
    statuses.register(
        direction="input",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error="fail_closed",
        timeout_seconds=0.1,
    )
    statuses.transition("input", "guard", DetectorState.HEALTHY, detector=detector)
    transitions.clear()
    app = _app_with_statuses(statuses)

    client = TestClient(app)
    assert client.get("/ready").status_code == 503
    assert client.get("/ready").status_code == 200
    assert client.get("/ready").status_code == 200

    assert transitions == [("healthy", "unhealthy"), ("unhealthy", "healthy")]
