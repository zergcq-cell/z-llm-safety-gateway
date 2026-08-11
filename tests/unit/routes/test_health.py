"""Unit tests for health check endpoints (/health, /ready, /metrics).

Test cases: TC-HEALTH-001~006
Covers: liveness probe, readiness probe (ready/not_ready), metrics content type,
        metrics placeholder body, health endpoints no authentication.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.routes.health import router, set_ready


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with only the health router (no middleware)."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for the minimal health-router app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_ready_state() -> None:
    """Reset the global _ready flag to False after each test.

    Prevents test pollution from set_ready(True) calls leaking into
    subsequent tests.
    """
    yield
    set_ready(False)


# ---------------------------------------------------------------------------
# TC-HEALTH-001: GET /health -> 200, {"status": "healthy"}, application/json
# ---------------------------------------------------------------------------


def test_health_liveness_probe_returns_healthy(client: TestClient) -> None:
    """TC-HEALTH-001: Liveness probe returns 200 with healthy status.

    GIVEN the FastAPI server is running
    WHEN the client sends GET /health
    THEN the server returns HTTP 200
    AND the response body is JSON {"status": "healthy"}
    AND the Content-Type is application/json
    AND the liveness probe does NOT check any external dependencies
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
    assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# TC-HEALTH-002: GET /ready (ready) -> 200, {"status": "ready"}
# ---------------------------------------------------------------------------


def test_ready_when_ready_returns_200(client: TestClient) -> None:
    """TC-HEALTH-002: Readiness probe returns 200 when server is ready.

    GIVEN the server configuration is loaded and provider clients initialized
    WHEN the client sends GET /ready
    THEN the server returns HTTP 200
    AND the response body is JSON {"status": "ready"}
    AND the Content-Type is application/json
    """
    set_ready(True)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# TC-HEALTH-003: GET /ready (not ready) -> 503, {"status": "not_ready"}
# ---------------------------------------------------------------------------


def test_ready_when_not_ready_returns_503(client: TestClient) -> None:
    """TC-HEALTH-003: Readiness probe returns 503 when server is not ready.

    GIVEN the server configuration is not loaded or provider clients not initialized
    WHEN the client sends GET /ready
    THEN the server returns HTTP 503
    AND the response body is JSON {"status": "not_ready"}
    AND the Content-Type is application/json
    """
    set_ready(False)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# TC-HEALTH-004: GET /metrics -> 200, Content-Type: text/plain; charset=utf-8
# ---------------------------------------------------------------------------


def test_metrics_returns_text_plain(client: TestClient) -> None:
    """TC-HEALTH-004: Metrics endpoint returns text/plain content type.

    GIVEN the FastAPI server is running
    WHEN the client sends GET /metrics
    THEN the server returns HTTP 200
    AND the Content-Type is text/plain; charset=utf-8
    """
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


# ---------------------------------------------------------------------------
# TC-HEALTH-005: GET /metrics -> placeholder body (Phase 1)
# ---------------------------------------------------------------------------


def test_metrics_returns_placeholder_body(client: TestClient) -> None:
    """TC-HEALTH-005: Metrics endpoint returns placeholder body in Phase 1.

    GIVEN the FastAPI server is running (Phase 1)
    WHEN the client sends GET /metrics
    THEN the response body is "# z LLM Safety Gateway metrics placeholder\\n"
    AND Phase 1 does NOT implement actual Prometheus metrics collection
    """
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.text == "# z LLM Safety Gateway metrics placeholder\n"


# ---------------------------------------------------------------------------
# TC-HEALTH-006: Health endpoints without auth -> no 401
# ---------------------------------------------------------------------------


def test_health_endpoints_without_auth_do_not_return_401(client: TestClient) -> None:
    """TC-HEALTH-006: Health endpoints are accessible without authentication.

    GIVEN the FastAPI server is running
    AND no authentication credentials are provided (no Authorization header)
    WHEN the client sends GET /health, GET /ready, GET /metrics
    THEN the server does NOT return 401 Unauthorized for any endpoint
    AND /health returns HTTP 200
    AND /ready returns HTTP 200 or 503 (depending on readiness state)
    AND /metrics returns HTTP 200
    """
    # Ensure no Authorization header is sent
    headers_without_auth: dict[str, str] = {}

    health_response = client.get("/health", headers=headers_without_auth)
    ready_response = client.get("/ready", headers=headers_without_auth)
    metrics_response = client.get("/metrics", headers=headers_without_auth)

    # None should return 401
    assert health_response.status_code != 401
    assert ready_response.status_code != 401
    assert metrics_response.status_code != 401

    # Specific status codes
    assert health_response.status_code == 200
    assert ready_response.status_code in (200, 503)
    assert metrics_response.status_code == 200
