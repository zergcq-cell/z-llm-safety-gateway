"""Unit tests for SafetyHeadersMiddleware and response header injection.

Test cases: TC-REQID-005~007
Covers: X-Request-ID response header injection (generated and propagated),
        X-Safety-Action: allow header injection.
"""

from __future__ import annotations

import re

import pytest

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ---------------------------------------------------------------------------
# TC-REQID-005: Generated ID -> response contains X-Request-ID header
# ---------------------------------------------------------------------------


def test_response_has_generated_request_id(client: pytest.fixture) -> None:
    """TC-REQID-005: Response contains X-Request-ID header when ID is generated.

    GIVEN the client sends a request without X-Request-ID header
    WHEN the server processes the request and returns a response
    THEN the response contains X-Request-ID header
    AND the X-Request-ID header value is the gateway-generated UUID v4
    """
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 36
    assert UUID_V4_PATTERN.match(request_id) is not None


# ---------------------------------------------------------------------------
# TC-REQID-006: Propagated ID -> response contains X-Request-ID with client value
# ---------------------------------------------------------------------------


def test_response_has_propagated_request_id(client: pytest.fixture) -> None:
    """TC-REQID-006: Response contains X-Request-ID with client-provided value.

    GIVEN the client sends a request with X-Request-ID: "my-req-123"
    WHEN the server processes the request and returns a response
    THEN the response contains X-Request-ID header
    AND the X-Request-ID header value is "my-req-123" (the client-provided value)
    """
    response = client.get("/test", headers={"X-Request-ID": "my-req-123"})

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"] == "my-req-123"


# ---------------------------------------------------------------------------
# TC-REQID-007: Any request -> response contains X-Safety-Action: "allow"
# ---------------------------------------------------------------------------


def test_response_has_safety_action_allow(client: pytest.fixture) -> None:
    """TC-REQID-007: All responses contain X-Safety-Action: "allow".

    GIVEN Phase 1 environment with the server running
    WHEN the client sends any request
    THEN the response contains X-Safety-Action header
    AND the X-Safety-Action header value is "allow"
    AND Phase 1 does not perform any safety detection
    """
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Safety-Action" in response.headers
    assert response.headers["X-Safety-Action"] == "allow"
