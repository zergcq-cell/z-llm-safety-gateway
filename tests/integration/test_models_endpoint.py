"""Integration tests for /v1/models endpoint — TC-FASTAPI-006.

Covers: model list passthrough from the first provider, no aggregation.
"""

from __future__ import annotations

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.routes.health import set_ready

TEST_CONFIG_YAML_TWO_PROVIDERS = """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "test-key"
  - name: "local_llama"
    type: "openai_compatible"
    base_url: "http://localhost:11434/v1"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"
    - pattern: "llama*"
      provider: "local_llama"

security:
  timeout:
    upstream: 5
"""


@pytest.fixture
def app(tmp_path: pytest.TempPathFactory) -> FastAPI:
    """Create a test FastAPI app with two providers configured."""
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(TEST_CONFIG_YAML_TWO_PROVIDERS)
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
# TC-FASTAPI-006: GET /v1/models — passthrough from first provider only.
# ---------------------------------------------------------------------------


@respx.mock
def test_list_models_passthrough_first_provider(client: TestClient) -> None:
    """TC-FASTAPI-006: GET /v1/models returns the first provider's model list.

    GIVEN a running gateway with two providers (openai, local_llama)
    WHEN the client sends GET /v1/models
    AND the mock openai provider returns a model list
    THEN the response status code matches the provider (200)
    AND the response body is the provider's model list (passthrough)
    AND only the first provider (openai) is queried, not local_llama (no aggregation)
    """
    openai_models_route = respx.get("https://api.openai.com/v1/models").respond(
        status_code=200,
        json={
            "object": "list",
            "data": [
                {"id": "gpt-4", "object": "model"},
                {"id": "gpt-3.5-turbo", "object": "model"},
            ],
        },
    )
    local_llama_route = respx.get("http://localhost:11434/v1/models").respond(
        status_code=200,
        json={
            "object": "list",
            "data": [{"id": "llama3", "object": "model"}],
        },
    )

    response = client.get("/v1/models")

    assert response.status_code == 200

    body = response.json()
    assert body["object"] == "list"
    model_ids = [m["id"] for m in body["data"]]
    assert "gpt-4" in model_ids
    assert "llama3" not in model_ids  # local_llama models NOT included

    # Only the first provider was queried
    assert openai_models_route.call_count == 1
    assert local_llama_route.call_count == 0
