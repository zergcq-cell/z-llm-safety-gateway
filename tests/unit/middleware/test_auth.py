"""Unit tests for AuthMiddleware.

Test cases: TC-AUTH-001~007
Covers: valid Bearer token allowed and injected, unknown token rejected (401),
        disabled auth pass-through, enabled fail-closed, OpenAI-compatible 401
        body without key leakage, request.state.api_key_name injection, and
        middleware ordering (RequestID before route protection).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.config.models import ApiKeyConfig, AuthConfig
from z_llm_safety_gateway.middleware.auth import AuthMiddleware
from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware

AUTH_HEADER = {"Authorization": "Bearer sk-a"}


def _create_app(
    auth: AuthConfig, *, include_request_id: bool = False
) -> FastAPI:
    """Create a test app with AuthMiddleware (and optionally RequestID).

    Ordering in Starlette: the last middleware added is outermost.  Adding
    Auth first (inner) then RequestID (outer) yields the production order
    RequestID -> Auth -> route.
    """
    app = FastAPI()
    app.add_middleware(AuthMiddleware, config=auth)
    if include_request_id:
        app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str | None]:
        return {"api_key_name": getattr(request.state, "api_key_name", None)}

    return app


# ---------------------------------------------------------------------------
# TC-AUTH-001: Valid Bearer token is allowed.
# ---------------------------------------------------------------------------


def test_valid_bearer_token_allowed() -> None:
    """TC-AUTH-001: A valid Bearer token matching a configured key is allowed.

    GIVEN security.auth.enabled=true and api_keys=[{key:'sk-a', name:'app-a'}]
    WHEN a request carries Authorization: Bearer sk-a
    THEN the request is allowed through to the route (HTTP 200)
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test", headers=AUTH_HEADER)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# TC-AUTH-002: Unknown Bearer token is rejected with 401.
# ---------------------------------------------------------------------------


def test_unknown_token_rejected() -> None:
    """TC-AUTH-002: An unknown Bearer token is rejected with HTTP 401.

    GIVEN security.auth.enabled=true and api_keys=[{key:'sk-a', name:'app-a'}]
    WHEN a request carries Authorization: Bearer sk-unknown (not configured)
    THEN the request is rejected with HTTP 401
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test", headers={"Authorization": "Bearer sk-unknown"})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# TC-AUTH-003: Disabled auth passes requests without credentials.
# ---------------------------------------------------------------------------


def test_disabled_auth_passes() -> None:
    """TC-AUTH-003: Disabled auth passes a request without an Authorization header.

    GIVEN security.auth.enabled is unset or false (default disabled)
    WHEN a request without any Authorization header reaches an endpoint
    THEN the request is allowed through (HTTP 200)
    """
    auth = AuthConfig(enabled=False, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# TC-AUTH-004: Enabled auth is fail-closed (no credentials -> 401).
# ---------------------------------------------------------------------------


def test_enabled_fail_closed() -> None:
    """TC-AUTH-004: Enabled auth rejects requests without credentials (fail-closed).

    GIVEN security.auth.enabled=true (explicitly enabled)
    WHEN a request without an Authorization header reaches an endpoint
    THEN the request is rejected with HTTP 401 (no credentials means deny)
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# TC-AUTH-005: 401 response is an OpenAI-compatible body that leaks no keys.
# ---------------------------------------------------------------------------


def test_401_openai_compatible_body() -> None:
    """TC-AUTH-005: 401 body is OpenAI-compatible and leaks no api_key values.

    GIVEN auth is enabled and the request token is invalid or missing
    WHEN AuthMiddleware rejects the request as unauthorized
    THEN the response is HTTP 401 with an OpenAI-compatible error body
    AND the error body contains an error object (with type and message fields)
    AND the response does NOT leak any configured api_key value
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test", headers={"Authorization": "Bearer sk-unknown"})

    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert "type" in body["error"]
    assert "message" in body["error"]
    # No configured or supplied key is reflected back to the client.
    assert "sk-a" not in response.text
    assert "sk-unknown" not in response.text


# ---------------------------------------------------------------------------
# TC-AUTH-006: request.state.api_key_name is injected on success.
# ---------------------------------------------------------------------------


def test_api_key_name_injected() -> None:
    """TC-AUTH-006: request.state.api_key_name is set to the matched key name.

    GIVEN auth is enabled and a Bearer token matches a key named 'app-a'
    WHEN the request proceeds into the route
    THEN request.state.api_key_name equals 'app-a'
    AND downstream middleware / audit logs can read request.state.api_key_name
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth))

    response = client.get("/test", headers=AUTH_HEADER)

    assert response.status_code == 200
    assert response.json()["api_key_name"] == "app-a"


# ---------------------------------------------------------------------------
# TC-AUTH-007: Middleware order — RequestID before, route protected.
# ---------------------------------------------------------------------------


def test_middleware_order() -> None:
    """TC-AUTH-007: Auth runs after RequestID and protects business endpoints.

    GIVEN auth is enabled and RequestIDMiddleware is registered outermost
    WHEN a request reaches the gateway
    THEN AuthMiddleware runs after RequestIDMiddleware and before routing
    AND all business endpoints are protected by auth
    AND RequestID still processes the request first (X-Request-ID present
        even on an auth-rejected response)
    """
    auth = AuthConfig(enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")])
    client = TestClient(_create_app(auth, include_request_id=True))

    # Route is protected: a request without credentials is rejected (401).
    rejected = client.get("/test")
    assert rejected.status_code == 401
    # RequestID ran first (outermost): the rejected response still carries
    # the X-Request-ID header.
    assert "X-Request-ID" in rejected.headers

    # A valid request passes through and RequestID still populates the header.
    allowed = client.get("/test", headers=AUTH_HEADER)
    assert allowed.status_code == 200
    assert "X-Request-ID" in allowed.headers
