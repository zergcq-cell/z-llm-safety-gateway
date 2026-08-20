"""Audit coverage for detector lifecycle and degraded requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import (
    _build_detector_transition_handler,
    _initialize_detectors,
)
from z_llm_safety_gateway.audit.models import AuditEntry, DetectorLifecycleEvent
from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.exceptions import DetectorInitializationError
from z_llm_safety_gateway.observability import metrics


class CaptureAudit:
    def __init__(self) -> None:
        self.entries: list[Any] = []
        self.lifecycle: list[str] = []

    def record(self, entry: Any) -> None:
        self.entries.append(entry)

    def flush(self) -> None:
        self.lifecycle.append("flush")

    def close(self) -> None:
        self.lifecycle.append("close")


class Provider:
    def __init__(self) -> None:
        self.config = type("Config", (), {"name": "provider"})()

    async def forward_request(
        self, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "safe"}}]},
        )


class Router:
    def __init__(self) -> None:
        self.provider = Provider()

    def route(self, model: str) -> Provider:
        return self.provider


class FailingRegistry:
    def register_from_entry_points(self, *, group: str) -> int:
        return 0

    async def create_detector(self, name: str, config: dict[str, Any]) -> Any:
        raise RuntimeError("secret-token https://private-endpoint")


def _app(tmp_path: Path, monkeypatch: Any) -> tuple[Any, CaptureAudit]:
    capture = CaptureAudit()
    monkeypatch.setattr("z_llm_safety_gateway.app.AuditLogger", lambda **kwargs: capture)
    path = tmp_path / "gateway.yaml"
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing:
  rules: [{pattern: "*", provider: local}]
pipeline:
  detectors: {input: [], output: []}
audit:
  enabled: true
  stdout: false
  file: {enabled: false}
"""
    )
    from z_llm_safety_gateway.app import create_app

    app = create_app(str(path))
    app.state.router = Router()
    return app, capture


def _set_issue(app: Any, *, on_error: str) -> None:
    statuses = DetectorStatusRegistry()
    statuses.register(
        direction="input",
        name="guard",
        detector_type="builtin",
        required=False,
        on_error=on_error,
        timeout_seconds=1.0,
    )
    statuses.transition("input", "guard", DetectorState.INITIALIZING)
    statuses.transition(
        "input",
        "guard",
        DetectorState.UNAVAILABLE,
        reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
    )
    app.state.detector_status_registry = statuses


def test_lifecycle_event_schema_and_state_change_deduplication() -> None:
    """TC-AUDIT-601: lifecycle audit has stable fields and deduplicates state."""
    audit = CaptureAudit()
    statuses = DetectorStatusRegistry(
        on_transition=_build_detector_transition_handler(audit)
    )
    statuses.register(
        direction="input",
        name="guard",
        detector_type="builtin",
        required=True,
        on_error="fail_closed",
        timeout_seconds=1.0,
    )
    statuses.transition("input", "guard", DetectorState.INITIALIZING)
    statuses.transition("input", "guard", DetectorState.INITIALIZING)
    statuses.transition(
        "input",
        "guard",
        DetectorState.UNAVAILABLE,
        reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
    )

    assert len(audit.entries) == 2
    event = audit.entries[-1]
    assert isinstance(event, DetectorLifecycleEvent)
    assert event.event_type == "detector_lifecycle"
    assert event.model_dump(exclude={"timestamp"}) == {
        "event_type": "detector_lifecycle",
        "detector_name": "guard",
        "direction": "input",
        "detector_type": "builtin",
        "old_state": "initializing",
        "new_state": "unavailable",
        "required": True,
        "on_error": "fail_closed",
        "reason_code": "initialization_error",
    }


def test_fatal_startup_flushes_and_closes_durable_lifecycle_audit(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """TC-AUDIT-602: real required startup failure persists then closes audit."""
    audit = CaptureAudit()
    monkeypatch.setattr("z_llm_safety_gateway.app.AuditLogger", lambda **kwargs: audit)
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry", lambda: FailingRegistry()
    )
    path = tmp_path / "fatal.yaml"
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing: {rules: [{pattern: "*", provider: local}]}
pipeline:
  detectors:
    input:
      - {name: prompt_injection, required: true, on_error: fail_closed}
    output: []
audit:
  enabled: true
  stdout: false
  file: {enabled: false}
"""
    )
    from z_llm_safety_gateway.app import create_app

    with pytest.raises(DetectorInitializationError):
        create_app(str(path))

    events = [entry for entry in audit.entries if isinstance(entry, DetectorLifecycleEvent)]
    assert events[-1].new_state == "unavailable"
    assert events[-1].reason_code == "initialization_error"
    assert audit.lifecycle == ["flush", "close"]


def test_fatal_startup_persists_lifecycle_to_real_file_sink(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """TC-AUDIT-602: fatal lifecycle evidence reaches the configured JSONL file."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry", lambda: FailingRegistry()
    )
    audit_dir = tmp_path / "audit"
    path = tmp_path / "fatal-file.yaml"
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing: {rules: [{pattern: "*", provider: local}]}
pipeline:
  detectors:
    input:
      - {name: prompt_injection, required: true, on_error: fail_closed}
    output: []
audit:
  enabled: true
  stdout: false
  file:
    enabled: true
    path: __AUDIT_DIR__
""".replace("__AUDIT_DIR__", str(audit_dir))
    )
    from z_llm_safety_gateway.app import create_app

    with pytest.raises(DetectorInitializationError):
        create_app(str(path))

    entries = [json.loads(line) for line in (audit_dir / "audit.log").read_text().splitlines()]
    fatal = next(
        entry
        for entry in entries
        if entry.get("event_type") == "detector_lifecycle"
        and entry.get("new_state") == "unavailable"
    )
    assert fatal["reason_code"] == "initialization_error"
    assert "secret-token" not in json.dumps(entries)


def test_fatal_startup_with_audit_disabled_keeps_sanitized_structured_log(
    tmp_path: Path, monkeypatch: Any, capsys: Any
) -> None:
    """TC-AUDIT-602: disabled audit still emits a stable fatal lifecycle signal."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.app.create_default_registry", lambda: FailingRegistry()
    )
    path = tmp_path / "fatal-disabled-audit.yaml"
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing: {rules: [{pattern: "*", provider: local}]}
pipeline:
  detectors:
    input:
      - {name: prompt_injection, required: true, on_error: fail_closed}
    output: []
audit:
  enabled: false
  stdout: false
  file: {enabled: false}
"""
    )
    from z_llm_safety_gateway.app import create_app

    with pytest.raises(DetectorInitializationError):
        create_app(str(path))

    output = capsys.readouterr().out
    assert "detector_initialization_failed" in output
    assert "initialization_error" in output
    assert "secret-token" not in output
    assert "https://private-endpoint" not in output


def test_request_audit_availability_order_is_stable(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """TC-AUDIT-603: multiple degraded detectors use stable identity ordering."""
    app, audit = _app(tmp_path, monkeypatch)
    statuses = DetectorStatusRegistry()
    for direction, name in [("output", "zeta"), ("input", "alpha")]:
        statuses.register(
            direction=direction,
            name=name,
            detector_type="builtin",
            required=False,
            on_error="fail_open",
            timeout_seconds=1.0,
        )
        statuses.transition(
            direction,
            name,
            DetectorState.UNAVAILABLE,
            reason_code=DetectorReasonCode.INITIALIZATION_ERROR,
        )
    app.state.detector_status_registry = statuses

    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    entry = next(item for item in audit.entries if isinstance(item, AuditEntry))
    assert [(item.direction, item.name) for item in entry.detector_availability] == [
        ("input", "alpha"),
        ("output", "zeta"),
    ]


def test_fail_open_request_audit_contains_availability(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """TC-DSV-001 / TC-AUDIT-603: continued request is explicitly degraded."""
    app, audit = _app(tmp_path, monkeypatch)
    _set_issue(app, on_error="fail_open")

    response = TestClient(app).post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    request_entries = [entry for entry in audit.entries if isinstance(entry, AuditEntry)]
    assert request_entries
    assert all(entry.safety_degraded is True for entry in request_entries)
    assert request_entries[0].detector_availability[0].model_dump() == {
        "name": "guard",
        "direction": "input",
        "state": "unavailable",
        "required": False,
        "on_error": "fail_open",
        "reason_code": "initialization_error",
    }


def test_fail_closed_503_records_request_audit(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """TC-DSV-002: fail-closed admission produces a blocked availability audit."""
    app, audit = _app(tmp_path, monkeypatch)
    _set_issue(app, on_error="fail_closed")

    response = TestClient(app).post(
        "/v1/chat/completions",
        json={
            "model": "test",
            "messages": [{"role": "user", "content": "private-body sk-live-123"}],
        },
    )

    assert response.status_code == 503
    entry = next(item for item in audit.entries if isinstance(item, AuditEntry))
    assert entry.final_action == "block"
    assert entry.safety_degraded is True
    assert entry.detector_availability[0].on_error == "fail_closed"
    external_signals = response.text + json.dumps(entry.to_json_line())
    assert "private-body" not in external_signals
    assert "sk-live-123" not in external_signals


@pytest.mark.asyncio
async def test_real_initialization_exception_is_sanitized_in_all_signals(
    capsys: Any,
) -> None:
    """TC-DSV-003 / TC-AUDIT-604: real failures expose only stable reason codes."""
    audit = CaptureAudit()
    metrics.set_enabled(True)
    statuses = DetectorStatusRegistry(
        on_transition=_build_detector_transition_handler(audit)
    )
    try:
        await _initialize_detectors(
            FailingRegistry(),
            {
                "prompt_injection": {
                    "required": False,
                    "on_error": "fail_open",
                    "timeout_seconds": 1.0,
                }
            },
            direction="input",
            status_registry=statuses,
            audit_logger=audit,
        )
        signals = "\n".join(
            [
                capsys.readouterr().out,
                json.dumps([entry.to_json_line() for entry in audit.entries]),
                metrics.generate_latest().decode(),
            ]
        )
    finally:
        metrics.set_enabled(False)

    assert "secret-token" not in signals
    assert "https://private-endpoint" not in signals
    assert "initialization_error" in signals
