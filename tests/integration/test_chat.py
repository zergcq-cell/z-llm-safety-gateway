"""Integration tests for /v1/chat/completions endpoint — TC-FASTAPI-003~005, 009~011.

Covers: normal request forwarding, model-not-found (404), invalid JSON (400),
provider HTTP 500 (502), provider timeout (502), provider HTTP 400 (502).
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.routes.health import set_ready

TEST_CONFIG_YAML = """
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

security:
  timeout:
    upstream: 5
"""


@pytest.fixture
def app(tmp_path: pytest.TempPathFactory) -> FastAPI:
    """Create a test FastAPI app with a valid config file."""
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(TEST_CONFIG_YAML)
    return create_app(str(config_path))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for the integration test app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_ready_state() -> None:
    """Reset the global _ready flag to False after each test."""
    yield
    set_ready(False)


# ---------------------------------------------------------------------------
# TC-FASTAPI-003: Normal request forwarding with 200 response.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_normal_forward(client: TestClient) -> None:
    """TC-FASTAPI-003: POST /v1/chat/completions with valid request returns provider response.

    GIVEN a running gateway with a configured openai provider
    WHEN the client sends POST /v1/chat/completions with model "gpt-4" and messages
    AND the mock provider returns 200 with a chat completion
    THEN the response status code is 200 (matching the provider)
    AND the response body is the provider's response (passthrough)
    AND the response contains X-Request-ID header
    AND the response contains X-Safety-Action: allow header
    """
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=200,
        json={
            "id": "chatcmpl-123",
            "choices": [{"message": {"role": "assistant", "content": "Hello"}}],
        },
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-safety-action"] == "allow"

    body = response.json()
    assert body["id"] == "chatcmpl-123"
    assert body["choices"][0]["message"]["content"] == "Hello"


# ---------------------------------------------------------------------------
# TC-FASTAPI-004: Model not found (no matching routing rule) → 404.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_model_not_found(client: TestClient) -> None:
    """TC-FASTAPI-004: POST /v1/chat/completions with unknown model returns 404.

    GIVEN a running gateway with routing rules for "gpt-4*" only
    WHEN the client sends POST /v1/chat/completions with model "claude-3-opus"
    THEN the response status code is 404
    AND the error.type is "invalid_request_error"
    AND the error.code is "model_not_found"
    AND the response contains X-Request-ID header
    """
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 404
    assert "x-request-id" in response.headers

    body = response.json()
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "model_not_found"


# ---------------------------------------------------------------------------
# TC-FASTAPI-005: Invalid JSON body → 400.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_invalid_json(client: TestClient) -> None:
    """TC-FASTAPI-005: POST /v1/chat/completions with invalid JSON returns 400.

    GIVEN a running gateway
    WHEN the client sends POST /v1/chat/completions with invalid JSON body
    THEN the response status code is 400
    AND the response body is in OpenAI-compatible error format
    AND the response contains X-Request-ID header
    """
    response = client.post(
        "/v1/chat/completions",
        content=b"{invalid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert "x-request-id" in response.headers

    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "type" in body["error"]


# ---------------------------------------------------------------------------
# TC-FASTAPI-009: Provider returns HTTP 500 → 502 provider_error.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_provider_500(client: TestClient) -> None:
    """TC-FASTAPI-009: Provider returning 500 results in 502 provider_error.

    GIVEN a running gateway with a configured openai provider
    WHEN the client sends POST /v1/chat/completions with model "gpt-4"
    AND the mock provider returns HTTP 500
    THEN the response status code is 502
    AND the error.type is "provider_error"
    AND the error message contains the provider name and original error info
    """
    respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=500,
        json={"error": {"message": "Internal server error"}},
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 502

    body = response.json()
    assert body["error"]["type"] == "provider_error"
    assert "openai" in body["error"]["message"].lower()


# ---------------------------------------------------------------------------
# TC-FASTAPI-010: Provider timeout → 502 provider_error with timeout message.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_provider_timeout(client: TestClient) -> None:
    """TC-FASTAPI-010: Provider timeout results in 502 provider_error with timeout message.

    GIVEN a running gateway with a configured openai provider (timeout=5s)
    WHEN the client sends POST /v1/chat/completions with model "gpt-4"
    AND the mock provider times out
    THEN the response status code is 502
    AND the error.type is "provider_error"
    AND the error message indicates a timeout
    """
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=httpx.ReadTimeout("Connection timed out"),
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 502

    body = response.json()
    assert body["error"]["type"] == "provider_error"
    assert "timeout" in body["error"]["message"].lower()


# ---------------------------------------------------------------------------
# TC-FASTAPI-011: Provider returns HTTP 400 → 502 provider_error, no retry.
# ---------------------------------------------------------------------------


@respx.mock
def test_chat_completions_provider_400_no_retry(client: TestClient) -> None:
    """TC-FASTAPI-011: Provider returning 400 results in 502 provider_error, no retry.

    GIVEN a running gateway with a configured openai provider
    WHEN the client sends POST /v1/chat/completions with model "gpt-4"
    AND the mock provider returns HTTP 400
    THEN the response status code is 502 (not 400)
    AND the error.type is "provider_error"
    AND the error message contains the original status code
    AND the provider is called exactly once (no retry)
    """
    mock_route = respx.post("https://api.openai.com/v1/chat/completions").respond(
        status_code=400,
        json={"error": {"message": "Bad request"}},
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 502

    body = response.json()
    assert body["error"]["type"] == "provider_error"
    assert "400" in body["error"]["message"]

    # No retry — provider called exactly once
    assert mock_route.call_count == 1
