"""Unit tests for AuthMiddleware.

Test cases: TC-AUTH-001~007
Covers: valid Bearer token allowed and injected, unknown token rejected (401),
        disabled auth pass-through, enabled fail-closed, OpenAI-compatible 401
        body without key leakage, request.state.api_key_name injection, and
        middleware ordering (RequestID before route protection).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.config.models import (
    ApiKeyConfig,
    AuthConfig,
    TenancyConfig,
    TenantConfig,
)
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


def test_legacy_auth_adds_default_tenant_context() -> None:
    """TC-AUTH-008: Legacy auth gains only the internal default tenant Context."""
    app = FastAPI()
    auth = AuthConfig(
        enabled=True,
        api_keys=[ApiKeyConfig(key="sk-legacy", name="legacy-app")],
    )
    app.add_middleware(AuthMiddleware, config=auth)

    @app.get("/legacy")
    async def legacy_endpoint(request: Request) -> dict[str, str]:
        context = request.state.tenant_context
        return {
            "api_key_name": request.state.api_key_name,
            "tenant_id": context.tenant_id,
            "identity_source": context.identity_source,
        }

    response = TestClient(app).get(
        "/legacy",
        headers={"Authorization": "Bearer sk-legacy"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "api_key_name": "legacy-app",
        "tenant_id": "default",
        "identity_source": "legacy_single_tenant",
    }

    duplicate_legacy = AuthConfig(
        enabled=False,
        api_keys=[
            ApiKeyConfig(key="same-legacy-key", name="first"),
            ApiKeyConfig(key="same-legacy-key", name="second"),
        ],
    )
    AuthMiddleware(FastAPI(), config=duplicate_legacy)


def test_multi_tenant_auth_compiles_validated_lookup() -> None:
    """TC-AUTH-009: Lookup compiles once and duplicate keys never overwrite."""
    tenancy = TenancyConfig(
        enabled=True,
        tenants=(TenantConfig(id="acme"), TenantConfig(id="globex")),
    )
    auth = AuthConfig(
        enabled=True,
        api_keys=[
            ApiKeyConfig(key="sk-acme", name="acme-app", tenant_id="acme"),
            ApiKeyConfig(key="sk-globex", name="globex-app", tenant_id="globex"),
        ],
    )
    middleware = AuthMiddleware(FastAPI(), config=auth, tenancy=tenancy)

    assert middleware._tenant_contexts["sk-acme"].tenant_id == "acme"
    assert middleware._tenant_contexts["sk-globex"].tenant_id == "globex"

    duplicate_auth = AuthConfig(
        enabled=True,
        api_keys=[
            ApiKeyConfig(key="same-key", name="a", tenant_id="acme"),
            ApiKeyConfig(key="same-key", name="b", tenant_id="globex"),
        ],
    )
    with pytest.raises(ValueError, match="duplicate_api_key"):
        AuthMiddleware(FastAPI(), config=duplicate_auth, tenancy=tenancy)


def test_tenant_auth_middleware_order_and_secret_safety(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-AUTH-010: Production chain resolves tenant before rate limiting."""
    from z_llm_safety_gateway.app import create_app

    config_path = tmp_path / "multi-tenant.yaml"
    config_path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - {name: local, type: openai_compatible, base_url: http://localhost:11434/v1}
routing:
  rules: [{pattern: "*", provider: local}]
tenancy:
  enabled: true
  tenants: [{id: acme}, {id: globex}]
security:
  auth:
    enabled: true
    api_keys:
      - {key: secret-acme, name: acme-app, tenant_id: acme}
      - {key: secret-globex, name: globex-app, tenant_id: globex}
  rate_limit: {enabled: true, rate: 1, burst: 1, per: api_key}
"""
    )
    app = create_app(str(config_path))

    @app.get("/tenant-order")
    async def tenant_order(request: Request) -> dict[str, str]:
        return {"tenant_id": request.state.tenant_context.tenant_id}

    auth_registration = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is AuthMiddleware
    )

    assert auth_registration.kwargs["tenancy"] is app.state.config.tenancy

    client = TestClient(app)
    for secret in ("secret-acme", "secret-globex"):
        response = client.get(
            "/tenant-order",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] in {"acme", "globex"}
        assert secret not in response.text

    rejected = client.get("/health")
    assert rejected.status_code == 401
    assert "X-Request-ID" in rejected.headers
    assert "secret-acme" not in rejected.text
    assert "secret-globex" not in rejected.text
    captured = capsys.readouterr()
    assert "secret-acme" not in captured.out
    assert "secret-acme" not in captured.err
    assert "secret-globex" not in captured.out
    assert "secret-globex" not in captured.err
