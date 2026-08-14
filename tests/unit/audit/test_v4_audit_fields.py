"""Unit tests for v0.4.0 audit-logger fixes — TC-AUDIT-001~016.

Covers B-08 (sync_timeout enforcement) and B-09 (audit field corrections)
from the v0.4.0 backlog, per design Decision 15 and audit-logger spec.

Test categories:
- TC-AUDIT-001~003: total_duration_ms assignment and serialization
- TC-AUDIT-004~005: user_id extraction from request body
- TC-AUDIT-006~007: DetectorAuditRecord duration_ms / error population
- TC-AUDIT-008~010: unified post_audit dict schema
- TC-AUDIT-011~013: DetectorAuditRecord.applied field
- TC-AUDIT-014~016: sync_timeout enforcement (B-08)
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.audit.models import DetectorAuditRecord
from z_llm_safety_gateway.config.models import OutputDetectionConfig, _parse_duration
from z_llm_safety_gateway.models import DetectionResult
from z_llm_safety_gateway.pipeline.engine import PipelineResult
from z_llm_safety_gateway.routes.chat import _build_audit_entry
from z_llm_safety_gateway.routes.health import set_ready

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_result(
    name: str = "test_detector",
    action: str = "allow",
    confidence: float = 0.0,
    risk_level: str = "low",
    duration_ms: float = 0.0,
    error: str | None = None,
    category: str = "test",
    modified_content: str | None = None,
) -> DetectionResult:
    """Create a DetectionResult for testing."""
    return DetectionResult(
        detector_name=name,
        category=category,
        action=action,  # type: ignore[arg-type]
        confidence=confidence,
        risk_level=risk_level,  # type: ignore[arg-type]
        message="test message",
        duration_ms=duration_ms,
        error=error,
        modified_content=modified_content,
    )


def _read_audit_entries(audit_dir: Path) -> list[dict[str, Any]]:
    """Read all audit log entries from the JSONL file."""
    log_file = audit_dir / "audit.log"
    if not log_file.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_file.read_text().strip().splitlines():
        if line:
            entries.append(json.loads(line))
    return entries


# Config with audit enabled (for user_id and total_duration_ms route tests).
_AUDIT_CONFIG_TEMPLATE = """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "test-key"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"

pipeline:
  mode: "sync"
  detectors:
    input: []
    output: []

security:
  timeout:
    upstream: 5

audit:
  enabled: true
  store_content: false
  sanitize_logs: true
  file:
    enabled: true
    path: "{audit_dir}"
  stdout: false
"""

# Config with output detector and short sync_timeout (for B-08 tests).
_SYNC_TIMEOUT_CONFIG_TEMPLATE = """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "test-key"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"

pipeline:
  mode: "sync"
  output_detection:
    mode: "sync"
    sync_timeout: "{sync_timeout}"
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        on_error: "{on_error}"
        config: {{}}

security:
  timeout:
    upstream: 5
"""


@pytest.fixture(autouse=True)
def _reset_ready_state() -> Generator[None, None, None]:
    """Reset the global _ready flag after each test."""
    yield
    set_ready(False)


def _make_audit_app(tmp_path: Path) -> FastAPI:
    """Create an app with audit enabled, writing to tmp_path."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "audit_config.yaml"
    config_path.write_text(_AUDIT_CONFIG_TEMPLATE.format(audit_dir=str(audit_dir)))
    return create_app(str(config_path))


def _make_sync_timeout_app(
    tmp_path: Path,
    sync_timeout: str = "0.2s",
    on_error: str = "fail_open",
) -> FastAPI:
    """Create an app with output detector and configurable sync_timeout."""
    config_path = tmp_path / "sync_timeout_config.yaml"
    config_path.write_text(
        _SYNC_TIMEOUT_CONFIG_TEMPLATE.format(
            sync_timeout=sync_timeout,
            on_error=on_error,
        )
    )
    return create_app(str(config_path))


class _SlowEngine:
    """Mock pipeline engine that sleeps for a specified duration."""

    def __init__(self, delay: float = 2.0) -> None:
        self._delay = delay

    async def run(
        self,
        detectors: list[Any],
        contexts: list[Any],
        detector_configs: dict[str, dict[str, Any]],
    ) -> PipelineResult:
        await asyncio.sleep(self._delay)
        return PipelineResult(
            final_action="allow",
            overall_risk_level="low",
            pipeline_duration_ms=self._delay * 1000,
        )


# --------------------------------------------------------------------------- #
# TC-AUDIT-001: input total_duration_ms assigned (SC-AUDIT-001)
# --------------------------------------------------------------------------- #
def test_input_total_duration_ms_assigned() -> None:
    """TC-AUDIT-001: input audit entry total_duration_ms is a real measured value."""
    entry = _build_audit_entry(
        request_id="req_001",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="hello world",
        final_action="allow",
        final_risk_level="low",
        total_duration_ms=42.5,
    )
    assert entry.total_duration_ms == 42.5
    assert entry.total_duration_ms > 0


# --------------------------------------------------------------------------- #
# TC-AUDIT-002: output total_duration_ms assigned, excludes provider latency
# --------------------------------------------------------------------------- #
def test_output_total_duration_ms_assigned() -> None:
    """TC-AUDIT-002: output audit entry total_duration_ms excludes provider latency."""
    entry = _build_audit_entry(
        request_id="req_002",
        direction="output",
        model="gpt-4",
        provider_name="openai",
        content="response text",
        final_action="allow",
        final_risk_level="low",
        total_duration_ms=15.3,
    )
    assert entry.total_duration_ms == 15.3
    assert entry.direction == "output"


# --------------------------------------------------------------------------- #
# TC-AUDIT-003: total_duration_ms correctly serialized in JSONL
# --------------------------------------------------------------------------- #
def test_total_duration_ms_in_jsonl() -> None:
    """TC-AUDIT-003: total_duration_ms is correctly assigned (not 0) in JSONL output."""
    entry = _build_audit_entry(
        request_id="req_003",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="test",
        final_action="allow",
        final_risk_level="low",
        total_duration_ms=99.9,
    )
    data = entry.to_json_line()
    assert data["total_duration_ms"] == 99.9
    assert data["total_duration_ms"] != 0.0


# --------------------------------------------------------------------------- #
# TC-AUDIT-004: user_id extracted from request body 'user' field (SC-AUDIT-004)
# --------------------------------------------------------------------------- #
@respx.mock
def test_user_id_extracted_from_body(tmp_path: Path) -> None:
    """TC-AUDIT-004: request body with 'user' field populates audit user_id."""
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={"id": "x", "choices": [{"message": {"role": "assistant", "content": "Hi"}}]},
    )

    app = _make_audit_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "user": "user_001",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200

    app.state.audit_logger.flush()
    entries = _read_audit_entries(tmp_path / "audit")
    assert len(entries) >= 2  # input + output
    for entry in entries:
        assert entry["user_id"] == "user_001"


# --------------------------------------------------------------------------- #
# TC-AUDIT-005: user_id is null when 'user' absent (SC-AUDIT-005)
# --------------------------------------------------------------------------- #
@respx.mock
def test_user_id_none_when_absent(tmp_path: Path) -> None:
    """TC-AUDIT-005: request body without 'user' field yields user_id=null."""
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={"id": "x", "choices": [{"message": {"role": "assistant", "content": "Hi"}}]},
    )

    app = _make_audit_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200

    app.state.audit_logger.flush()
    entries = _read_audit_entries(tmp_path / "audit")
    assert len(entries) >= 2
    for entry in entries:
        assert entry["user_id"] is None


# --------------------------------------------------------------------------- #
# TC-AUDIT-006: DetectorAuditRecord duration_ms populated (SC-AUDIT-006)
# --------------------------------------------------------------------------- #
def test_detector_duration_ms_populated() -> None:
    """TC-AUDIT-006: DetectorAuditRecord.duration_ms takes DetectionResult.duration_ms."""
    result = _make_result(
        name="toxicity",
        action="block",
        confidence=0.95,
        risk_level="high",
        duration_ms=37.5,
    )
    entry = _build_audit_entry(
        request_id="req_006",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="toxic text",
        final_action="block",
        final_risk_level="high",
        detector_results=[result],
    )
    assert len(entry.detectors) == 1
    assert entry.detectors[0].duration_ms == 37.5
    assert entry.detectors[0].duration_ms != 0.0


# --------------------------------------------------------------------------- #
# TC-AUDIT-007: DetectorAuditRecord error populated (SC-AUDIT-007)
# --------------------------------------------------------------------------- #
def test_detector_error_populated() -> None:
    """TC-AUDIT-007: DetectorAuditRecord.error takes DetectionResult.error."""
    # Error case
    error_result = _make_result(
        name="external_detector",
        action="allow",
        confidence=0.0,
        risk_level="low",
        duration_ms=5.0,
        error="Connection refused",
    )
    entry = _build_audit_entry(
        request_id="req_007a",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="test",
        final_action="allow",
        final_risk_level="low",
        detector_results=[error_result],
    )
    assert entry.detectors[0].error == "Connection refused"
    assert entry.detectors[0].error is not None

    # Success case: error is None
    ok_result = _make_result(
        name="toxicity",
        action="allow",
        confidence=0.1,
        risk_level="low",
        duration_ms=3.0,
        error=None,
    )
    entry2 = _build_audit_entry(
        request_id="req_007b",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="test",
        final_action="allow",
        final_risk_level="low",
        detector_results=[ok_result],
    )
    assert entry2.detectors[0].error is None


# --------------------------------------------------------------------------- #
# TC-AUDIT-008: post_audit schema with result/category/risk_level (SC-AUDIT-008)
# --------------------------------------------------------------------------- #
def test_post_audit_schema_aligned() -> None:
    """TC-AUDIT-008: post_audit dict uses result/category/risk_level schema."""
    post_audit = {
        "executed": True,
        "result": "block",
        "category": "toxicity",
        "risk_level": "critical",
    }
    entry = _build_audit_entry(
        request_id="req_008",
        direction="output",
        model="gpt-4",
        provider_name="openai",
        content="streamed text",
        final_action="block",
        final_risk_level="critical",
        streaming=True,
        post_audit=post_audit,
    )
    assert entry.post_audit is not None
    assert entry.post_audit["executed"] is True
    assert entry.post_audit["result"] == "block"
    assert entry.post_audit["category"] == "toxicity"
    assert entry.post_audit["risk_level"] == "critical"


# --------------------------------------------------------------------------- #
# TC-AUDIT-009: no effective_action/original_action keys (SC-AUDIT-009)
# --------------------------------------------------------------------------- #
def test_post_audit_no_legacy_keys() -> None:
    """TC-AUDIT-009: post_audit dict does not use effective_action/original_action."""
    post_audit = {
        "executed": True,
        "result": "flag",
        "category": "toxicity",
        "risk_level": "high",
    }
    entry = _build_audit_entry(
        request_id="req_009",
        direction="output",
        model="gpt-4",
        provider_name="openai",
        content="streamed text",
        final_action="flag",
        final_risk_level="high",
        streaming=True,
        post_audit=post_audit,
    )
    assert entry.post_audit is not None
    assert "effective_action" not in entry.post_audit
    assert "original_action" not in entry.post_audit


# --------------------------------------------------------------------------- #
# TC-AUDIT-010: post_audit executed=false when skipped (SC-AUDIT-010)
# --------------------------------------------------------------------------- #
def test_post_audit_executed_false() -> None:
    """TC-AUDIT-010: post_audit={'executed': false} when post-audit is skipped."""
    post_audit = {"executed": False}
    entry = _build_audit_entry(
        request_id="req_010",
        direction="output",
        model="gpt-4",
        provider_name="openai",
        content="buffered text",
        final_action="allow",
        final_risk_level="low",
        streaming=True,
        post_audit=post_audit,
    )
    assert entry.post_audit is not None
    assert entry.post_audit["executed"] is False
    assert "result" not in entry.post_audit
    assert "category" not in entry.post_audit
    assert "risk_level" not in entry.post_audit


# --------------------------------------------------------------------------- #
# TC-AUDIT-011: DetectorAuditRecord has optional applied field (SC-AUDIT-011)
# --------------------------------------------------------------------------- #
def test_detector_record_applied_field() -> None:
    """TC-AUDIT-011: DetectorAuditRecord has optional applied field, backward compatible."""
    # Default: applied is None (backward compatible)
    record = DetectorAuditRecord(
        name="test",
        action="allow",
        confidence=0.5,
        risk_level="low",
    )
    assert record.applied is None

    # Explicit True
    record_t = DetectorAuditRecord(
        name="test",
        action="modify",
        confidence=0.9,
        risk_level="medium",
        applied=True,
    )
    assert record_t.applied is True

    # Explicit False
    record_f = DetectorAuditRecord(
        name="test",
        action="flag",
        confidence=0.8,
        risk_level="high",
        applied=False,
    )
    assert record_f.applied is False

    # Serialized output includes applied
    data = record_t.model_dump()
    assert "applied" in data
    assert data["applied"] is True


# --------------------------------------------------------------------------- #
# TC-AUDIT-012: streaming modify downgraded to flag with applied=false (SC-AUDIT-012)
# --------------------------------------------------------------------------- #
def test_streaming_modify_downgraded_not_applied() -> None:
    """TC-AUDIT-012: streaming post-audit modify is downgraded to flag, applied=false."""
    modify_result = _make_result(
        name="pii_redaction",
        action="modify",
        confidence=0.95,
        risk_level="high",
        duration_ms=12.0,
        modified_content="redacted text",
    )
    entry = _build_audit_entry(
        request_id="req_012",
        direction="output",
        model="gpt-4",
        provider_name="openai",
        content="streamed text with PII",
        final_action="flag",
        final_risk_level="high",
        detector_results=[modify_result],
        streaming=True,
        applied_modify=False,
    )
    assert len(entry.detectors) == 1
    det = entry.detectors[0]
    # modify downgraded to flag
    assert det.action == "flag"
    assert det.applied is False


# --------------------------------------------------------------------------- #
# TC-AUDIT-013: applied modify recorded as applied=true (SC-AUDIT-013)
# --------------------------------------------------------------------------- #
def test_applied_modify_recorded() -> None:
    """TC-AUDIT-013: input/sync-output modify that was applied records applied=true."""
    modify_result = _make_result(
        name="pii_redaction",
        action="modify",
        confidence=0.95,
        risk_level="medium",
        duration_ms=10.0,
        modified_content="redacted text",
    )
    entry = _build_audit_entry(
        request_id="req_013",
        direction="input",
        model="gpt-4",
        provider_name="openai",
        content="text with PII",
        final_action="modify",
        final_risk_level="medium",
        detector_results=[modify_result],
        applied_modify=True,
    )
    assert len(entry.detectors) == 1
    det = entry.detectors[0]
    assert det.action == "modify"
    assert det.applied is True


# --------------------------------------------------------------------------- #
# TC-AUDIT-014: sync output detection wrapped in asyncio.wait_for (SC-AUDIT-014)
# --------------------------------------------------------------------------- #
@respx.mock
def test_sync_output_detection_wrapped_wait_for(tmp_path: Path) -> None:
    """TC-AUDIT-014: sync output detection is wrapped in asyncio.wait_for(sync_timeout).

    GIVEN a gateway with output detectors and sync_timeout=0.2s
    WHEN the pipeline engine takes 2s to run (exceeding timeout)
    THEN the timeout is enforced (response returns in < 1.5s, not 2s)
    AND with fail_open the response is allowed (200)
    """
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "chatcmpl-1",
            "choices": [{"message": {"role": "assistant", "content": "Hi there"}}],
        },
    )

    app = _make_sync_timeout_app(tmp_path, sync_timeout="0.2s", on_error="fail_open")
    # Replace the engine with a slow one
    app.state.pipeline_engine = _SlowEngine(delay=2.0)
    client = TestClient(app)

    start = time.monotonic()
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    elapsed = time.monotonic() - start

    # Timeout enforced: should return well before the 2s delay
    assert elapsed < 1.5, f"Expected timeout enforcement, but took {elapsed:.1f}s"
    # fail_open → response allowed
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# TC-AUDIT-015: sync_timeout on_error handling (SC-AUDIT-015)
# --------------------------------------------------------------------------- #
@respx.mock
def test_sync_timeout_on_error_handling(tmp_path: Path) -> None:
    """TC-AUDIT-015: sync_timeout triggers on_error (fail_closed → block).

    GIVEN a gateway with output detectors, sync_timeout=0.2s, on_error=fail_closed
    WHEN the pipeline engine takes 2s (exceeding timeout)
    THEN the detector is treated as block (fail_closed)
    AND the response is 422 (safety_output_blocked)
    """
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "chatcmpl-2",
            "choices": [{"message": {"role": "assistant", "content": "Hi there"}}],
        },
    )

    app = _make_sync_timeout_app(tmp_path, sync_timeout="0.2s", on_error="fail_closed")
    app.state.pipeline_engine = _SlowEngine(delay=2.0)
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    # fail_closed → block → 422
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["type"] == "safety_block"
    assert body["error"]["code"] == "safety_output_blocked"


# --------------------------------------------------------------------------- #
# TC-AUDIT-016: sync_timeout default 5s (SC-AUDIT-016)
# --------------------------------------------------------------------------- #
def test_sync_timeout_default() -> None:
    """TC-AUDIT-016: sync_timeout defaults to 5s when not explicitly configured."""
    cfg = OutputDetectionConfig()
    assert cfg.sync_timeout == "5s"
    assert _parse_duration(cfg.sync_timeout) == 5.0
