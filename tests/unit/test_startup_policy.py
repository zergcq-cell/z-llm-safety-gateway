"""Application startup policy tests for detector availability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry
from z_llm_safety_gateway.exceptions import DetectorInitializationError


class DummyDetector:
    def __init__(self, name: str) -> None:
        self.name = name

    async def shutdown(self) -> None:
        return None


class ControlledRegistry:
    def __init__(self, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()

    def register_from_entry_points(self, *, group: str) -> int:
        return 0

    async def create_detector(self, name: str, config: dict[str, Any]) -> DummyDetector:
        if name in self.fail_names:
            raise RuntimeError("secret endpoint and token")
        return DummyDetector(name)


class ProviderSpy:
    def __init__(self) -> None:
        self.calls = 0
        self.config = type("Config", (), {"name": "spy"})()

    async def forward_request(
        self, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        self.calls += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )


class RouterSpy:
    def __init__(self, provider: ProviderSpy) -> None:
        self.provider = provider

    def route(self, model: str) -> ProviderSpy:
        return self.provider


def _write_config(tmp_path: Path, detectors_yaml: str) -> str:
    path = tmp_path / "gateway.yaml"
    path.write_text(
        f"""
server:
  host: 127.0.0.1
  port: 8080
providers:
  - name: local
    type: openai_compatible
    base_url: http://localhost:11434/v1
routing:
  rules:
    - pattern: "*"
      provider: local
pipeline:
  detectors:
{detectors_yaml}
audit:
  enabled: false
  stdout: false
  file:
    enabled: false
observability:
  metrics:
    enabled: false
"""
    )
    return str(path)


def test_optional_fail_closed_startup_is_not_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-RDP-003: optional fail_closed failure keeps a diagnostic app not-ready."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry",
        lambda: ControlledRegistry({"prompt_injection"}),
    )
    config = _write_config(
        tmp_path,
        """    input:
      - name: prompt_injection
        on_error: fail_closed
    output: []""",
    )

    from z_llm_safety_gateway.app import create_app

    app = create_app(config)
    assert app.state.ready is False
    assert app.state.detector_status_registry.issues(strict=True)[0].name == "prompt_injection"
    assert TestClient(app).get("/ready").status_code == 503
    provider = ProviderSpy()
    app.state.router = RouterSpy(provider)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 503
    assert provider.calls == 0


def test_optional_fail_open_startup_is_ready_but_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-RDP-004: optional fail_open failure permits an explicit degraded app."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry",
        lambda: ControlledRegistry({"prompt_injection"}),
    )
    config = _write_config(
        tmp_path,
        """    input:
      - name: prompt_injection
        on_error: fail_open
    output: []""",
    )

    from z_llm_safety_gateway.app import create_app

    app = create_app(config)
    assert app.state.ready is True
    assert [item.name for item in app.state.detector_status_registry.issues(strict=False)] == [
        "prompt_injection"
    ]
    ready_response = TestClient(app).get("/ready")
    assert ready_response.status_code == 200
    assert ready_response.json()["degraded"] is True
    provider = ProviderSpy()
    app.state.router = RouterSpy(provider)
    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    assert provider.calls == 1


def test_multiple_failures_use_strictest_policy_and_stable_order() -> None:
    """TC-RDP-005: strict issues win and all issue ordering is deterministic."""
    statuses = DetectorStatusRegistry()
    for direction, name, on_error in [
        ("output", "zeta", "fail_open"),
        ("input", "beta", "fail_closed"),
        ("input", "alpha", "fail_open"),
    ]:
        statuses.register(
            direction=direction,
            name=name,
            detector_type="builtin",
            required=False,
            on_error=on_error,
            timeout_seconds=1.0,
        )
        statuses.transition(direction, name, DetectorState.UNAVAILABLE)

    assert [(item.direction, item.name) for item in statuses.issues()] == [
        ("input", "alpha"),
        ("input", "beta"),
        ("output", "zeta"),
    ]
    assert [item.name for item in statuses.issues(strict=True)] == ["beta"]


def test_create_app_stores_all_configured_detector_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-FAST-601: app state includes successful and unavailable directions."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry",
        lambda: ControlledRegistry({"secret_leak"}),
    )
    config = _write_config(
        tmp_path,
        """    input:
      - name: prompt_injection
        on_error: fail_open
    output:
      - name: secret_leak
        on_error: fail_open""",
    )

    from z_llm_safety_gateway.app import create_app

    app = create_app(config)
    snapshot = app.state.detector_status_registry.snapshot()
    assert [(item.direction, item.name, item.state.value) for item in snapshot] == [
        ("input", "prompt_injection", "healthy"),
        ("output", "secret_leak", "unavailable"),
    ]


def test_required_startup_failure_propagates_before_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-FAST-602: required startup failure propagates and never marks ready."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry",
        lambda: ControlledRegistry({"prompt_injection"}),
    )
    config = _write_config(
        tmp_path,
        """    input:
      - name: prompt_injection
        required: true
        on_error: fail_closed
    output: []""",
    )

    from z_llm_safety_gateway.app import create_app

    with pytest.raises(DetectorInitializationError):
        create_app(config)
