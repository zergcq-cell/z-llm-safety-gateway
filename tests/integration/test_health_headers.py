"""Integration tests for health endpoints with middleware (X-Request-ID injection).

Test cases: TC-HEALTH-007~009
Covers: X-Request-ID header injection by RequestIDMiddleware on /health, /ready,
        /metrics endpoints. Verifies UUID v4 format when no client-provided ID.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware
from z_llm_safety_gateway.routes.health import router, set_ready

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with RequestID and SafetyHeaders middleware.

    Middleware registration order matters in Starlette:
    - SafetyHeaders added first  -> inner (closer to routes, processes response first)
    - RequestID   added second   -> outer (first to process request, last for response)

    Request flow:  RequestID -> SafetyHeaders -> route handler
    Response flow: route handler -> SafetyHeaders -> RequestID
    """
    test_app = FastAPI()
    test_app.state.ready = True
    test_app.add_middleware(SafetyHeadersMiddleware)
    test_app.add_middleware(RequestIDMiddleware)
    test_app.include_router(router)
    return test_app


@pytest.fixture
def app() -> FastAPI:
    """Test FastAPI application with both middlewares and health router."""
    return create_test_app()


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
# TC-HEALTH-007: GET /health (no X-Request-ID) -> response has X-Request-ID (UUID v4)
# ---------------------------------------------------------------------------


def test_health_response_contains_request_id(client: TestClient) -> None:
    """TC-HEALTH-007: /health response contains X-Request-ID in UUID v4 format.

    GIVEN the FastAPI server is running with RequestID middleware registered
    WHEN the client sends GET /health without X-Request-ID header
    THEN the response contains X-Request-ID header
    AND the X-Request-ID value is in UUID v4 format
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    request_id = response.headers["X-Request-ID"]
    assert UUID_V4_PATTERN.match(request_id) is not None


# ---------------------------------------------------------------------------
# TC-HEALTH-008: GET /ready (no X-Request-ID) -> response has X-Request-ID (UUID v4)
# ---------------------------------------------------------------------------


def test_ready_response_contains_request_id(client: TestClient) -> None:
    """TC-HEALTH-008: /ready response contains X-Request-ID in UUID v4 format.

    GIVEN the FastAPI server is running with RequestID middleware registered
    WHEN the client sends GET /ready without X-Request-ID header
    THEN the response contains X-Request-ID header
    AND the X-Request-ID value is in UUID v4 format
    """
    response = client.get("/ready")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    request_id = response.headers["X-Request-ID"]
    assert UUID_V4_PATTERN.match(request_id) is not None


# ---------------------------------------------------------------------------
# TC-HEALTH-009: GET /metrics (no X-Request-ID) -> response has X-Request-ID (UUID v4)
# ---------------------------------------------------------------------------


def test_metrics_response_contains_request_id(client: TestClient) -> None:
    """TC-HEALTH-009: /metrics response contains X-Request-ID in UUID v4 format.

    v0.4.0: /metrics is controlled by observability.metrics.enabled (default off).
    When disabled, /metrics returns 404, but X-Request-ID is still injected by
    the RequestID middleware (outermost in the chain).

    GIVEN the FastAPI server is running with RequestID middleware registered
    WHEN the client sends GET /metrics without X-Request-ID header
    THEN the response contains X-Request-ID header
    AND the X-Request-ID value is in UUID v4 format
    """
    response = client.get("/metrics")

    # metrics disabled by default → 404, but middleware still injects request ID
    assert response.status_code == 404
    assert "X-Request-ID" in response.headers

    request_id = response.headers["X-Request-ID"]
    assert UUID_V4_PATTERN.match(request_id) is not None
