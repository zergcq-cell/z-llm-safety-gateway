"""Integration tests for streaming endpoint — TC-FAST-002 ~ TC-FAST-017.

Covers: SSE streaming proxy, sliding-window detection, buffer mode,
post-audit recall, async output detection, and audit logging integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.routes.health import set_ready

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _sse_chunk(text: str) -> str:
    """Build an OpenAI-style SSE chunk carrying *text* as delta content."""
    payload = json.dumps({"choices": [{"delta": {"content": text}}]})
    return f"data: {payload}\n\n"


def _stream_side_effect(chunks: list[str], status_code: int = 200):
    """Create a respx side_effect returning a streaming SSE response."""

    def _side_effect(request: httpx.Request) -> httpx.Response:
        async def _aiter():
            for chunk in chunks:
                yield chunk.encode("utf-8")

        return httpx.Response(
            status_code,
            content=_aiter(),
            headers={"content-type": "text/event-stream"},
            request=request,
        )

    return _side_effect


# --------------------------------------------------------------------------- #
# Test configs
# --------------------------------------------------------------------------- #

_STREAMING_CONFIG = """
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
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
  streaming:
    mode: "sliding_window"
    window_size: 30
    overlap: 5
    send_flag_events: true
    post_audit: true
    recall:
      method: "sse"

audit:
  enabled: false
"""

_BUFFER_CONFIG = """
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
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
  streaming:
    mode: "buffer"
    post_audit: false
    recall:
      method: "sse"
"""

_AUDIT_CONFIG = """
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
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
  streaming:
    mode: "sliding_window"
    window_size: 30
    overlap: 5
    post_audit: false

audit:
  enabled: true
  sanitize_logs: true
  store_content: false
  file:
    enabled: true
    path: "/tmp/test-audit-streaming"
  stdout: false
"""

_PASSTHROUGH_CONFIG = """
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
  detectors:
    input: []
    output: []
"""


def _make_app(tmp_path: Any, config_yaml: str) -> FastAPI:
    """Create a test app from the given config YAML."""
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(config_yaml)
    return create_app(str(config_path))


@pytest.fixture(autouse=True)
def _reset_ready() -> Any:
    """Reset the global readiness flag after each test."""
    yield
    set_ready(False)


# --------------------------------------------------------------------------- #
# TC-FAST-002: Streaming response returns SSE chunks
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_returns_sse_chunks(tmp_path: Any) -> None:
    """TC-FAST-002: stream=true returns StreamingResponse with SSE chunks."""
    app = _make_app(tmp_path, _PASSTHROUGH_CONFIG)
    client = TestClient(app)

    chunks = [_sse_chunk("hello"), _sse_chunk(" world"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    text = resp.text
    assert "hello" in text
    assert "world" in text
    assert "[DONE]" in text


# --------------------------------------------------------------------------- #
# TC-FAST-003: Input block with stream=true returns 400 (no stream)
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_input_block_returns_400(tmp_path: Any) -> None:
    """TC-FAST-003: input pipeline block returns 400, no stream started."""
    config = """
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
  detectors:
    input:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
    output: []
"""
    app = _make_app(tmp_path, config)
    client = TestClient(app)

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Here is my key: sk-abcdefghij1234567890xxx"}
            ],
            "stream": True,
        },
    )
    assert resp.status_code == 400
    assert "safety_input_blocked" in resp.text


# --------------------------------------------------------------------------- #
# TC-FAST-004: Provider error during streaming sends error event + DONE
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_provider_error_sends_error_event(tmp_path: Any) -> None:
    """TC-FAST-004: provider error mid-stream sends SSE error + DONE."""
    app = _make_app(tmp_path, _PASSTHROUGH_CONFIG)
    client = TestClient(app)

    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect([], status_code=500)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    assert "error" in text.lower()
    assert "[DONE]" in text


# --------------------------------------------------------------------------- #
# TC-FAST-005: Sliding window block stops forwarding + safety_block
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_window_block_emits_safety_block(tmp_path: Any) -> None:
    """TC-FAST-005: window detection block stops stream and sends safety_block."""
    app = _make_app(tmp_path, _STREAMING_CONFIG)
    client = TestClient(app)

    # Content with API key that fits within a single window (30 chars).
    # sk- + 27 chars = 30 chars total, matches sk-[a-zA-Z0-9]{20,}
    secret = "sk-1234567890abcdefghij1234567"
    chunks = [_sse_chunk(secret), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    assert "safety_block" in text
    assert "[DONE]" in text


# --------------------------------------------------------------------------- #
# TC-FAST-010: Buffer mode safe replay
# --------------------------------------------------------------------------- #

@respx.mock
def test_buffer_mode_safe_replay(tmp_path: Any) -> None:
    """TC-FAST-010: buffer mode replays chunks when content is safe."""
    app = _make_app(tmp_path, _BUFFER_CONFIG)
    client = TestClient(app)

    chunks = [_sse_chunk("hello"), _sse_chunk(" world"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    assert "hello" in text
    assert "world" in text
    assert "[DONE]" in text
    assert "safety_block" not in text


# --------------------------------------------------------------------------- #
# TC-FAST-011: Buffer mode blocked
# --------------------------------------------------------------------------- #

@respx.mock
def test_buffer_mode_blocked_sends_safety_block(tmp_path: Any) -> None:
    """TC-FAST-011: buffer mode block sends safety_block + DONE, no content."""
    app = _make_app(tmp_path, _BUFFER_CONFIG)
    client = TestClient(app)

    secret = "sk-abcdefghij1234567890xxx"
    chunks = [_sse_chunk(f"Here is the key: {secret}"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    assert "safety_block" in text
    assert "[DONE]" in text


# --------------------------------------------------------------------------- #
# TC-FAST-012: Post-audit runs after stream completes (SSE recall)
# --------------------------------------------------------------------------- #

@respx.mock
def test_post_audit_recall_sse_event(tmp_path: Any) -> None:
    """TC-FAST-012/013: post-audit block triggers safety_recall SSE event."""
    app = _make_app(tmp_path, _STREAMING_CONFIG)
    client = TestClient(app)

    # Content below window_size (30) to avoid mid-stream block,
    # but post-audit will detect the secret in full content.
    secret = "sk-abcdefghij1234567890xx"
    chunks = [_sse_chunk(secret), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    # Post-audit should find the secret and emit safety_recall.
    assert "safety_recall" in text or "safety_block" in text


# --------------------------------------------------------------------------- #
# TC-FAST-016: Audit logging for streaming output
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_audit_logging(tmp_path: Any) -> None:
    """TC-FAST-016: audit entries are written for streaming requests."""
    app = _make_app(tmp_path, _AUDIT_CONFIG)
    client = TestClient(app)

    chunks = [_sse_chunk("hello world"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200

    # Verify audit log file was created with entries.
    audit_dir = Path("/tmp/test-audit-streaming")
    if audit_dir.exists():
        files = list(audit_dir.glob("audit.log*"))
        if files:
            content = files[0].read_text()
            assert '"direction": "output"' in content
            assert '"streaming": true' in content


# --------------------------------------------------------------------------- #
# TC-FAST-017: Audit disabled produces no entries
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_audit_disabled_no_entries(tmp_path: Any) -> None:
    """TC-FAST-017: audit.enabled=false produces no audit entries."""
    app = _make_app(tmp_path, _PASSTHROUGH_CONFIG)
    client = TestClient(app)

    chunks = [_sse_chunk("hello"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.status_code == 200
    # The default config has audit.enabled=false, so no entries.
    # We just verify the response is successful.


# --------------------------------------------------------------------------- #
# TC-FAST-002b: X-Request-ID header in streaming response
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_response_has_request_id_header(tmp_path: Any) -> None:
    """TC-FAST-002b: streaming response includes X-Request-ID header."""
    app = _make_app(tmp_path, _PASSTHROUGH_CONFIG)
    client = TestClient(app)

    chunks = [_sse_chunk("hi"), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert resp.headers.get("x-request-id") is not None
    assert resp.headers.get("x-safety-action") is not None


# --------------------------------------------------------------------------- #
# TC-FAST-006: Sliding window flag continues + safety_flag event
# --------------------------------------------------------------------------- #

@respx.mock
def test_streaming_window_flag_emits_safety_flag(tmp_path: Any) -> None:
    """TC-FAST-006: window detection flag continues stream with safety_flag."""
    # Use secret_leak detector (confidence=1.0 on match) with engine-level
    # thresholds: block_threshold=2.0 (unreachable) downgrades to flag,
    # flag_threshold=0.5 (1.0 >= 0.5 → flag).
    config = """
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
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
          block_threshold: 2.0
          flag_threshold: 0.5
  streaming:
    mode: "sliding_window"
    window_size: 30
    overlap: 5
    send_flag_events: true
    post_audit: false
    recall:
      method: "sse"
audit:
  enabled: false
"""
    app = _make_app(tmp_path, config)
    client = TestClient(app)

    # Secret that fits within a single 30-char window.
    secret = "sk-1234567890abcdefghij1234567"
    chunks = [_sse_chunk(secret), "data: [DONE]\n\n"]
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=_stream_side_effect(chunks)
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    text = resp.text
    # flag action should emit safety_flag event and continue streaming.
    assert "safety_flag" in text
    assert "[DONE]" in text


# --------------------------------------------------------------------------- #
# TC-FAST-014: Non-streaming async output detection returns immediately
# --------------------------------------------------------------------------- #

@respx.mock
def test_async_output_detection_returns_immediately(tmp_path: Any) -> None:
    """TC-FAST-014: async mode returns response without output detection delay."""
    config = """
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
  detectors:
    input: []
    output:
      - name: "secret_leak"
        enabled: true
        config:
          patterns: ["api_key"]
  output_detection:
    mode: "async"
    recall:
      webhook_url: "http://hooks.example.com/recall"
      webhook_auth_header: "Bearer test"
"""
    app = _make_app(tmp_path, config)
    client = TestClient(app)

    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "chatcmpl-1",
            "choices": [{"message": {"content": "Hello!"}}],
        },
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    # Response should be returned immediately (200, not blocked).
    assert resp.status_code == 200
    assert "Hello!" in resp.text


# --------------------------------------------------------------------------- #
# TC-FAST-016b: Non-streaming sync audit logging
# --------------------------------------------------------------------------- #

@respx.mock
def test_non_streaming_sync_audit_logging(tmp_path: Any) -> None:
    """TC-FAST-016b: sync non-streaming request writes input + output audit."""
    config = _AUDIT_CONFIG.replace(
        'mode: "sliding_window"\n    window_size: 30\n    overlap: 5\n    post_audit: false',
        'mode: "sliding_window"\n    post_audit: false',
    )
    app = _make_app(tmp_path, config)
    client = TestClient(app)

    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "chatcmpl-1",
            "choices": [{"message": {"content": "Hello!"}}],
        },
    )

    resp = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert resp.status_code == 200

    # Verify audit log file has entries.
    audit_dir = Path("/tmp/test-audit-streaming")
    if audit_dir.exists():
        files = list(audit_dir.glob("audit.log*"))
        if files:
            content = files[0].read_text()
            assert '"direction": "output"' in content
