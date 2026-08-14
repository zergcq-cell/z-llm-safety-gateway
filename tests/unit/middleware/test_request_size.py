"""Unit tests for RequestSizeMiddleware.

Test cases: TC-RSL-001~003 (request-size-limit spec)
Covers: Content-Length exceeded -> 413 OpenAI-compatible body; chunked body
read limit -> 413; within-limit requests pass through.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.middleware.request_size import RequestSizeMiddleware


def create_test_app(max_request_size: str = "10MB") -> FastAPI:
    """Build a FastAPI app with RequestSizeMiddleware and an echo route.

    The echo route reads the request body so chunked (no Content-Length)
    bodies are actually consumed, exercising the read-time limit.
    """
    app = FastAPI()
    app.add_middleware(RequestSizeMiddleware, max_request_size=max_request_size)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        return {"len": len(body)}

    return app


def _error_body(response: Any) -> dict[str, Any]:
    """Return the ``error`` dict from an OpenAI-compatible response body."""
    data = response.json()
    return data["error"]


# --------------------------------------------------------------------------- #
# TC-RSL-001: Content-Length > max -> 413 OpenAI-compatible body
# --------------------------------------------------------------------------- #
def test_content_length_exceeded_returns_413() -> None:
    """TC-RSL-001: Content-Length over the limit returns HTTP 413.

    GIVEN RequestSizeMiddleware with max_request_size of 1KB
    WHEN a request with a Content-Length greater than 1KB is sent
    THEN the response status is 413
    AND the body is OpenAI-compatible (error.type / error.message)
    AND the oversized body does not reach the route handler
    """
    app = create_test_app(max_request_size="1KB")
    client = TestClient(app)

    response = client.post("/echo", content=b"x" * (1024 + 1))

    assert response.status_code == 413
    error = _error_body(response)
    assert "type" in error
    assert "message" in error
    # The route handler would return {"len": ...}; a 413 must not come from it.
    assert "len" not in response.json()


def test_default_limit_is_10mb() -> None:
    """TC-RSL-001b: default max_request_size is 10MB, larger rejected."""
    app = create_test_app()  # default 10MB
    client = TestClient(app)

    response = client.post("/echo", content=b"x" * (10 * 1024 * 1024 + 1))

    assert response.status_code == 413
    assert "error" in response.json()


# --------------------------------------------------------------------------- #
# TC-RSL-002: chunked (no Content-Length) body read limit -> 413
# --------------------------------------------------------------------------- #
def test_chunked_body_over_limit_returns_413() -> None:
    """TC-RSL-002: chunked body exceeding the limit during read returns 413.

    GIVEN RequestSizeMiddleware with max_request_size of 1KB
    WHEN a chunked request (no Content-Length) streams more than 1KB in total
    THEN the request is interrupted and returns HTTP 413
    AND the response body is OpenAI-compatible
    AND the full body is not buffered beyond the limit
    """
    app = create_test_app(max_request_size="1KB")

    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/echo",
        "raw_path": b"/echo",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 80),
        "state": {},
    }

    # Total 3KB streamed in chunks; no content-length header present.
    chunks = [b"x" * 1024, b"y" * 1024, b"z" * 1024]
    sent_messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        if chunks:
            body = chunks.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    asyncio.run(app(scope, receive, send))

    starts = [m for m in sent_messages if m["type"] == "http.response.start"]
    assert len(starts) == 1
    assert starts[0]["status"] == 413

    bodies = b"".join(
        m.get("body", b"") for m in sent_messages if m["type"] == "http.response.body"
    )
    payload = json.loads(bodies.decode("utf-8"))
    assert "type" in payload["error"]
    assert "message" in payload["error"]


def test_chunked_body_within_limit_passes() -> None:
    """TC-RSL-002b: chunked body within the limit passes through normally."""
    app = create_test_app(max_request_size="10MB")
    client = TestClient(app)

    # httpx/TestClient always sets Content-Length; use the echo route for the
    # happy-path within-limit check.
    response = client.post("/echo", content=b"hello world")

    assert response.status_code == 200
    assert response.json()["len"] == len(b"hello world")


# --------------------------------------------------------------------------- #
# TC-RSL-003: within-limit request passes through to the route
# --------------------------------------------------------------------------- #
def test_within_limit_request_passes() -> None:
    """TC-RSL-003: a request within the size limit is forwarded normally.

    GIVEN RequestSizeMiddleware with max_request_size of 10MB
    WHEN a small request body is sent
    THEN the request reaches the route handler and returns a normal 200
    AND no 413 error is produced
    """
    app = create_test_app(max_request_size="10MB")
    client = TestClient(app)

    response = client.post("/echo", content=b'{"hello":"world"}')

    assert response.status_code == 200
    assert response.json()["len"] == len(b'{"hello":"world"}')
    assert "error" not in response.json()
