"""Shared fixtures for middleware unit tests."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware


def create_test_app() -> FastAPI:
    """Create a test FastAPI app with RequestID and SafetyHeaders middleware.

    Middleware registration order matters in Starlette:
    - SafetyHeaders added first  -> inner (closer to routes, processes response first)
    - RequestID   added second    -> outer (first to process request, last to process response)

    Request flow:  RequestID -> SafetyHeaders -> route handler
    Response flow: route handler -> SafetyHeaders -> RequestID
    """
    app = FastAPI()
    app.add_middleware(SafetyHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    return app


@pytest.fixture
def app() -> FastAPI:
    """Test FastAPI application with both middlewares registered."""
    return create_test_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for the test app."""
    return TestClient(app)


@pytest.fixture
def make_request(client: TestClient) -> Any:
    """Helper to make requests with optional headers."""

    def _make_request(
        headers: dict[str, str] | None = None,
    ) -> Any:
        return client.get("/test", headers=headers or {})

    return _make_request
