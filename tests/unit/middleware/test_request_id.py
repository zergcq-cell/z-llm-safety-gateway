"""Unit tests for RequestIDMiddleware.

Test cases: TC-REQID-001~004, TC-REQID-008~010
Covers: UUID v4 generation, client ID propagation, invalid ID sanitization,
        request.state storage, UUID v4 format validation, X-Safety-Risk-Level absence.
"""

from __future__ import annotations

import re
import uuid as uuid_module

import pytest

UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def is_valid_uuid_v4(value: str) -> bool:
    """Check if a string is a valid UUID v4."""
    try:
        parsed = uuid_module.UUID(value, version=4)
        return str(parsed) == value and parsed.version == 4
    except (ValueError, AttributeError, TypeError):
        return False


# ---------------------------------------------------------------------------
# TC-REQID-001: Request without X-Request-ID -> generate UUID v4
# ---------------------------------------------------------------------------


def test_generate_uuid_when_absent(client: pytest.fixture) -> None:
    """TC-REQID-001: Request without X-Request-ID header generates UUID v4.

    GIVEN the client sends a request without X-Request-ID header
    WHEN the RequestID middleware processes the request
    THEN a UUID v4 is generated as the request ID
    AND the UUID v4 conforms to the 36-character format xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    """
    response = client.get("/test")

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    assert request_id is not None
    assert len(request_id) == 36
    assert is_valid_uuid_v4(request_id)


# ---------------------------------------------------------------------------
# TC-REQID-002: Valid X-Request-ID -> use client value
# ---------------------------------------------------------------------------


def test_use_client_id_when_valid(client: pytest.fixture) -> None:
    """TC-REQID-002: Valid X-Request-ID is used as-is.

    GIVEN the client sends X-Request-ID: "my-req-123" matching ^[a-zA-Z0-9_-]{1,128}$
    WHEN the RequestID middleware processes the request
    THEN the client-provided value "my-req-123" is used
    AND no new UUID v4 is generated
    """
    response = client.get("/test", headers={"X-Request-ID": "my-req-123"})

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    assert request_id == "my-req-123"


# ---------------------------------------------------------------------------
# TC-REQID-003: Invalid X-Request-ID -> discard and generate UUID v4
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_id",
    [
        "invalid request id",      # contains spaces
        "req/id",                  # contains slash
        "req'; DROP TABLE--",      # contains special chars (SQL injection attempt)
        "a" * 129,                 # exceeds 128 char limit
        "req\nid",                 # contains newline (log injection attempt)
        "req\r\nX-Injected: true",  # CRLF injection attempt
    ],
    ids=["spaces", "slash", "special_chars", "too_long", "newline", "crlf_injection"],
)
def test_discard_invalid_client_id(
    client: pytest.fixture, invalid_id: str
) -> None:
    """TC-REQID-003: Invalid X-Request-ID is discarded and new UUID v4 generated.

    GIVEN the client sends X-Request-ID with a value that does NOT match
          ^[a-zA-Z0-9_-]{1,128}$ (contains special chars, exceeds 128 chars, etc.)
    WHEN the RequestID middleware processes the request
    THEN the invalid client ID is discarded
    AND a new UUID v4 is generated as the request ID
    AND this behavior prevents log injection and header injection
    """
    response = client.get("/test", headers={"X-Request-ID": invalid_id})

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    # The invalid ID must NOT be used
    assert request_id != invalid_id
    # A new UUID v4 must be generated
    assert len(request_id) == 36
    assert is_valid_uuid_v4(request_id)


# ---------------------------------------------------------------------------
# TC-REQID-004: Empty X-Request-ID -> discard and generate UUID v4
# ---------------------------------------------------------------------------


def test_discard_empty_client_id(client: pytest.fixture) -> None:
    """TC-REQID-004: Empty X-Request-ID header is discarded and new UUID v4 generated.

    GIVEN the client sends X-Request-ID: "" (empty string)
    WHEN the RequestID middleware processes the request
    THEN the empty ID is discarded
    AND a new UUID v4 is generated as the request ID
    """
    response = client.get("/test", headers={"X-Request-ID": ""})

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    assert request_id != ""
    assert len(request_id) == 36
    assert is_valid_uuid_v4(request_id)


# ---------------------------------------------------------------------------
# TC-REQID-008: X-Safety-Action "allow" -> no X-Safety-Risk-Level header
# ---------------------------------------------------------------------------


def test_no_risk_level_when_allow(client: pytest.fixture) -> None:
    """TC-REQID-008: When X-Safety-Action is "allow", X-Safety-Risk-Level is absent.

    GIVEN Phase 1 environment with SafetyHeaders middleware active
    AND the response X-Safety-Action is "allow"
    WHEN the server returns the response
    THEN the response does NOT contain X-Safety-Risk-Level header
    """
    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers.get("X-Safety-Action") == "allow"
    assert "X-Safety-Risk-Level" not in response.headers


# ---------------------------------------------------------------------------
# TC-REQID-009: request.state.request_id contains the request ID (string type)
# ---------------------------------------------------------------------------


def test_request_id_stored_in_state(client: pytest.fixture) -> None:
    """TC-REQID-009: request.state.request_id stores the request ID as a string.

    GIVEN the RequestID middleware has processed the request and determined the request ID
    WHEN the route handler or downstream middleware accesses request.state
    THEN request.state.request_id contains the request ID value
    AND request.state.request_id is a string type
    """
    response = client.get("/test")

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    assert request_id is not None
    assert isinstance(request_id, str)
    assert len(request_id) > 0


# ---------------------------------------------------------------------------
# TC-REQID-010: Generated UUID v4 format validation
# ---------------------------------------------------------------------------


def test_generated_uuid_v4_format(client: pytest.fixture) -> None:
    """TC-REQID-010: Generated UUID v4 conforms to standard format.

    GIVEN the client request does not carry X-Request-ID header
    WHEN the gateway generates a request ID
    THEN the generated ID is UUID v4 format
    AND the ID is 36 characters long
    AND the ID matches ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$
    AND the 14th character (index 14) is '4' (UUID version 4)
    AND the 19th character (index 19) is '8', '9', 'a', or 'b' (RFC 4122 variant)
    """
    response = client.get("/test")

    assert response.status_code == 200
    body = response.json()
    request_id = body["request_id"]

    # 36 characters
    assert len(request_id) == 36

    # Matches UUID v4 regex
    assert UUID_V4_PATTERN.match(request_id) is not None

    # 14th character (0-indexed) is '4' — UUID version
    assert request_id[14] == "4"

    # 19th character (0-indexed) is 8/9/a/b — RFC 4122 variant
    assert request_id[19] in ("8", "9", "a", "b")
