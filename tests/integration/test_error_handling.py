"""Integration tests for error handling — TC-FASTAPI-007, 012~013.

Covers: config host/port verification, ConfigError → 500, unhandled Exception → 500.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.exceptions import ConfigError
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
# TC-FASTAPI-007: Config loads server.host and server.port correctly.
# ---------------------------------------------------------------------------


def test_config_loads_host_and_port(app: FastAPI) -> None:
    """TC-FASTAPI-007: Config with server.host=127.0.0.1 and port=8080 is loaded correctly.

    GIVEN a config file with server.host="127.0.0.1" and server.port=8080
    WHEN create_app loads the config
    THEN app.state.config.server.host is "127.0.0.1"
    AND app.state.config.server.port is 8080
    """
    assert app.state.config.server.host == "127.0.0.1"
    assert app.state.config.server.port == 8080


# ---------------------------------------------------------------------------
# TC-FASTAPI-012: ConfigError during request → 500 internal_error, config_error.
# ---------------------------------------------------------------------------


def test_config_error_returns_500(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-FASTAPI-012: ConfigError during request returns 500 with config_error code.

    GIVEN a running gateway
    WHEN a request triggers a ConfigError (mocked router.route)
    THEN the response status code is 500
    AND the error.type is "internal_error"
    AND the error.code is "config_error"
    AND the response body does not expose secrets from the exception
    """

    def raise_config_error(model: str) -> None:
        raise ConfigError("Config error with secret-key-12345")

    monkeypatch.setattr(app.state.router, "route", raise_config_error)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 500

    body = response.json()
    assert body["error"]["type"] == "internal_error"
    assert body["error"]["code"] == "config_error"

    # Secrets must not be exposed in the response body
    assert "secret-key-12345" not in response.text


# ---------------------------------------------------------------------------
# TC-FASTAPI-013: Unhandled exception → 500 internal_error, no details in body.
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_500(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-FASTAPI-013: Unhandled exception returns 500 without exposing details.

    GIVEN a running gateway
    WHEN a request triggers an unhandled RuntimeError (mocked router.route)
    THEN the response status code is 500
    AND the error.type is "internal_error"
    AND the exception details are NOT exposed in the response body

    Note: Uses raise_server_exceptions=False so the ServerErrorMiddleware
    catches the exception and invokes the registered Exception handler
    instead of re-raising in the TestClient.
    """

    def raise_runtime_error(model: str) -> None:
        raise RuntimeError("Unexpected error with sensitive-data-67890")

    monkeypatch.setattr(app.state.router, "route", raise_runtime_error)

    # raise_server_exceptions=False lets ServerErrorMiddleware handle the
    # exception and return the handler's JSON response to the client.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )

    assert response.status_code == 500

    body = response.json()
    assert body["error"]["type"] == "internal_error"

    # Exception details must not be exposed in the response body
    assert "sensitive-data-67890" not in response.text
    assert "Unexpected error" not in response.text
