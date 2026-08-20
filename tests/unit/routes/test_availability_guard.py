"""Business admission tests for detector availability."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry


class ProviderSpy:
    def __init__(self) -> None:
        self.forward_calls = 0
        self.stream_calls = 0
        self.config = type("Config", (), {"name": "spy"})()

    async def forward_request(
        self, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        self.forward_calls += 1
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "choices": [{"message": {"role": "assistant", "content": "safe"}}],
            },
        )

    async def stream_forward(self, body: dict[str, Any], headers: dict[str, str]) -> Any:
        self.stream_calls += 1
        if False:
            yield b""


class RouterSpy:
    def __init__(self, provider: ProviderSpy) -> None:
        self.provider = provider
        self.route_calls = 0

    def route(self, model: str) -> ProviderSpy:
        self.route_calls += 1
        return self.provider


class DetectorSpy:
    name = "runtime-guard"

    def __init__(self) -> None:
        self.detect_calls = 0

    async def detect(self, content: str, context: Any) -> Any:
        self.detect_calls += 1
        raise AssertionError("unhealthy fail-open detector must be skipped")


def _app(
    tmp_path: Path,
    *,
    output_mode: str = "sync",
) -> tuple[Any, RouterSpy, ProviderSpy]:
    path = tmp_path / "gateway.yaml"
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing:
  rules:
    - {pattern: "*", provider: local}
pipeline:
  detectors: {input: [], output: []}
  output_detection:
    mode: __OUTPUT_MODE__
    recall:
      webhook_url: http://localhost/recall
audit:
  enabled: false
  stdout: false
  file: {enabled: false}
""".replace("__OUTPUT_MODE__", output_mode)
    )
    from z_llm_safety_gateway.app import create_app

    app = create_app(str(path))
    provider = ProviderSpy()
    router = RouterSpy(provider)
    app.state.router = router
    return app, router, provider


def _issue(
    app: Any,
    *,
    direction: str,
    on_error: str,
    state: DetectorState = DetectorState.UNAVAILABLE,
    detector: Any | None = None,
) -> None:
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction=direction,
        name="guard",
        detector_type="builtin",
        required=False,
        on_error=on_error,
        timeout_seconds=1.0,
    )
    statuses.transition(direction, "guard", DetectorState.INITIALIZING)
    statuses.transition(direction, "guard", state, detector=detector)
    app.state.detector_status_registry = statuses


def _body(**extra: Any) -> dict[str, Any]:
    return {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
        **extra,
    }


def test_input_fail_closed_preflight_returns_exact_503_without_provider(
    tmp_path: Path,
) -> None:
    """TC-FAST-603: input strict issue returns the dedicated availability error."""
    app, router, provider = _app(tmp_path)
    _issue(app, direction="input", on_error="fail_closed")

    response = TestClient(app).post("/v1/chat/completions", json=_body())

    assert response.status_code == 503
    assert response.headers["X-Safety-Action"] == "block"
    assert response.json() == {
        "error": {
            "message": "Safety detection is temporarily unavailable",
            "type": "safety_unavailable",
            "code": "safety_detector_unavailable",
            "safety": {"affected_directions": ["input"], "detectors": ["guard"]},
        }
    }
    assert router.route_calls == 0
    assert provider.forward_calls == 0


@pytest.mark.parametrize(
    ("body", "output_mode"),
    [
        (_body(), "sync"),
        (_body(stream=True), "sync"),
        (_body(), "async"),
    ],
    ids=["sync", "stream", "async-output-mode"],
)
def test_output_fail_closed_preflight_blocks_every_response_mode(
    tmp_path: Path, body: dict[str, Any], output_mode: str
) -> None:
    """TC-FAST-604: output strict issue blocks sync/stream/async before Provider."""
    app, router, provider = _app(tmp_path, output_mode=output_mode)
    _issue(app, direction="output", on_error="fail_closed")

    response = TestClient(app).post("/v1/chat/completions", json=body)

    assert response.status_code == 503
    assert response.json()["error"]["safety"]["affected_directions"] == ["output"]
    assert router.route_calls == 0
    assert provider.forward_calls == 0
    assert provider.stream_calls == 0


def test_fail_open_issue_skips_detector_and_allows_provider(
    tmp_path: Path,
) -> None:
    """TC-FAST-605: fail-open issue skips the unhealthy detector and continues."""
    app, router, provider = _app(tmp_path)
    detector = DetectorSpy()
    app.state.input_detectors = [detector]
    app.state.input_detector_configs = {"guard": {"on_error": "fail_open"}}
    _issue(
        app,
        direction="input",
        on_error="fail_open",
        state=DetectorState.UNHEALTHY,
        detector=detector,
    )

    response = TestClient(app).post("/v1/chat/completions", json=_body())

    assert response.status_code == 200
    assert detector.detect_calls == 0
    assert router.route_calls == 1
    assert provider.forward_calls == 1


def test_streaming_post_audit_uses_request_filtered_detectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-FAST-605: post-audit cannot reintroduce a skipped unhealthy detector."""
    from z_llm_safety_gateway.routes import chat as chat_module

    app, _, provider = _app(tmp_path)
    healthy = DetectorSpy()
    unhealthy = DetectorSpy()
    captured: list[list[Any]] = []

    class RunnerSpy:
        def __init__(
            self,
            engine: Any,
            output_detectors: list[Any],
            detector_configs: dict[str, dict[str, Any]],
        ) -> None:
            captured.append(output_detectors)

    monkeypatch.setattr(chat_module, "PostAuditRunner", RunnerSpy)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                streaming_config=None,
                output_detectors=[healthy, unhealthy],
                output_detector_configs={},
                streaming_webhook_recall=None,
            )
        ),
        state=SimpleNamespace(output_detectors=[healthy], safety_action="allow"),
    )

    chat_module._build_streaming_response(
        request=request,
        body={"stream": True},
        provider=provider,
        forward_headers={},
        request_id="r1",
        model="test",
        engine=object(),
        audit_logger=None,
        audit_enabled=False,
    )

    assert captured == [[healthy]]
