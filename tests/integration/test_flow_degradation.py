"""Request snapshot degradation and admission integration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.flow.evidence import NodeStatus
from z_llm_safety_gateway.observability.flow import sanitize_observable_value
from z_llm_safety_gateway.routes.chat import _enforce_detector_availability


def _issue_registry(*, on_error: str) -> DetectorStatusRegistry:
    registry = DetectorStatusRegistry()
    registry.register(
        direction="output",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error=on_error,
        timeout_seconds=1.0,
    )
    registry.transition(
        "output",
        "guard",
        DetectorState.UNAVAILABLE,
        reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
    )
    return registry


def test_tc_dsv_701() -> None:
    """TC-DSV-701: fail-open degradation is frozen and evidenced per stage."""
    registry = _issue_registry(on_error="fail_open")
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                detector_status_registry=registry,
                input_detectors=[],
                output_detectors=[],
                input_detector_configs={},
                output_detector_configs={},
            )
        ),
        state=SimpleNamespace(request_id="request"),
    )

    _enforce_detector_availability(request)
    snapshot = request.state.flow_snapshot
    registry.transition("output", "guard", DetectorState.HEALTHY)
    evidence = snapshot.stage("output", "post-audit").evidence

    assert request.state.safety_degraded is True
    assert snapshot.degraded is True
    assert snapshot.status("output", "guard").state is DetectorState.UNAVAILABLE
    assert evidence.nodes[0].status is NodeStatus.SKIPPED
    assert evidence.nodes[0].degraded is True


def test_tc_dsv_702(tmp_path: Path) -> None:
    """TC-DSV-702: strict output admission produces evidence before Provider use."""
    config_path = tmp_path / "gateway.yaml"
    config_path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing: {rules: [{pattern: "*", provider: local}]}
pipeline: {detectors: {input: [], output: []}}
audit: {enabled: false, stdout: false, file: {enabled: false}}
"""
    )
    from z_llm_safety_gateway.app import create_app

    app = create_app(str(config_path))

    class Provider:
        calls = 0
        config = SimpleNamespace(name="provider")

        async def forward_request(self, body: Any, headers: Any) -> httpx.Response:
            del body, headers
            self.calls += 1
            return httpx.Response(200, json={})

    provider = Provider()
    app.state.router = SimpleNamespace(route=lambda model: provider)
    app.state.detector_status_registry = _issue_registry(on_error="fail_closed")
    captured: dict[str, Any] = {}
    original = _enforce_detector_availability

    def capture(request: Any) -> None:
        try:
            original(request)
        finally:
            captured["snapshot"] = request.state.flow_snapshot
            captured["evidence"] = tuple(request.state.flow_evidence)

    from z_llm_safety_gateway.routes import chat as chat_module

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(chat_module, "_enforce_detector_availability", capture)
        response = TestClient(app).post(
            "/v1/chat/completions",
            json={"model": "model", "messages": [{"role": "user", "content": "x"}]},
        )

    assert response.status_code == 503
    assert response.headers["X-Safety-Action"] == "block"
    assert response.json()["error"]["code"] == "safety_detector_unavailable"
    assert provider.calls == 0
    assert captured["snapshot"].strict_issues
    assert captured["evidence"][0].nodes[0].status is NodeStatus.SKIPPED


def test_tc_dsv_703() -> None:
    """TC-DSV-703: degradation reasons stay distinct, bounded, and payload-free."""
    timeout, timeout_sanitized = sanitize_observable_value(
        "reason_code", "node_timeout"
    )
    unavailable, unavailable_sanitized = sanitize_observable_value(
        "reason_code", "capability_unavailable"
    )
    rejected, rejected_signal = sanitize_observable_value(
        "reason_code",
        "RuntimeError(secret=https://private-endpoint/" + "x" * 300 + ")",
    )

    assert (timeout, unavailable) == ("node_timeout", "capability_unavailable")
    assert timeout_sanitized is False
    assert unavailable_sanitized is False
    assert rejected == "invalid"
    assert rejected_signal is True
    assert "secret" not in rejected
