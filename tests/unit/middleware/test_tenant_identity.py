"""Trusted request-scoped tenant identity tests."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.config.models import (
    ApiKeyConfig,
    AuthConfig,
    TenancyConfig,
    TenantConfig,
)
from z_llm_safety_gateway.middleware.auth import AuthMiddleware


def _tenant_app(auth: AuthConfig, tenancy: TenancyConfig) -> FastAPI:
    app = FastAPI()
    app.state.provider_name = "global-provider"
    app.add_middleware(AuthMiddleware, config=auth, tenancy=tenancy)

    @app.get("/inspect")
    async def inspect(request: Request) -> dict[str, Any]:
        context = request.state.tenant_context
        immutable = False
        try:
            context.tenant_id = "mutated"
        except FrozenInstanceError:
            immutable = True
        return {
            "contract_version": context.contract_version,
            "tenant_id": context.tenant_id,
            "identity_source": context.identity_source,
            "api_key_name": getattr(request.state, "api_key_name", None),
            "immutable": immutable,
            "fields": sorted(context.__dataclass_fields__),
            "provider_name": request.app.state.provider_name,
        }

    return app


def _multi_tenant_auth() -> tuple[AuthConfig, TenancyConfig]:
    auth = AuthConfig(
        enabled=True,
        api_keys=[
            ApiKeyConfig(
                key="secret-acme",
                name="acme-app",
                tenant_id="acme",
            )
        ],
    )
    tenancy = TenancyConfig(enabled=True, tenants=(TenantConfig(id="acme"),))
    return auth, tenancy


def test_bound_key_assigns_frozen_tenant_context() -> None:
    """TC-TIC-001: A bound key assigns a frozen secret-free Context v1.0."""
    auth, tenancy = _multi_tenant_auth()
    response = TestClient(_tenant_app(auth, tenancy)).get(
        "/inspect",
        headers={"Authorization": "Bearer secret-acme"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "contract_version": "1.0",
        "tenant_id": "acme",
        "identity_source": "api_key",
        "api_key_name": "acme-app",
        "immutable": True,
        "fields": ["contract_version", "identity_source", "tenant_id"],
        "provider_name": "global-provider",
    }
    assert "secret-acme" not in response.text


def test_invalid_credentials_never_create_tenant_context() -> None:
    """TC-TIC-004: Invalid credentials fail closed without a tenant fallback."""
    auth, tenancy = _multi_tenant_auth()
    client = TestClient(_tenant_app(auth, tenancy))

    for headers in ({}, {"Authorization": "Bearer secret-invalid"}):
        response = client.get("/inspect", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_api_key"
        assert "secret-acme" not in response.text
        assert "secret-invalid" not in response.text


def test_tenant_resolution_uses_precompiled_lookup() -> None:
    """TC-TIC-005: Request-time resolution uses construction-time key lookup."""
    tenant_ids = tuple(f"tenant-{index}" for index in range(1024))
    auth = AuthConfig(
        enabled=True,
        api_keys=[
            ApiKeyConfig(
                key=f"secret-{index}",
                name=f"app-{index}",
                tenant_id=tenant_ids[index % len(tenant_ids)],
            )
            for index in range(4096)
        ],
    )
    tenancy = TenancyConfig(
        enabled=True,
        tenants=tuple(TenantConfig(id=tenant_id) for tenant_id in tenant_ids),
    )
    app = _tenant_app(auth, tenancy)
    client = TestClient(app)

    initial = client.get(
        "/inspect",
        headers={"Authorization": "Bearer secret-4095"},
    )
    assert initial.status_code == 200

    class LookupOnlyDict(dict[str, Any]):
        get_calls = 0

        def get(self, key: str, default: Any = None) -> Any:
            self.get_calls += 1
            return super().get(key, default)

        def __iter__(self):
            raise AssertionError("request-time lookup must not iterate")

        def keys(self):
            raise AssertionError("request-time lookup must not scan keys")

        def values(self):
            raise AssertionError("request-time lookup must not scan values")

        def items(self):
            raise AssertionError("request-time lookup must not scan items")

    middleware: Any = app.middleware_stack
    while not isinstance(middleware, AuthMiddleware):
        middleware = middleware.app
    assert len(middleware._keys) == 4096
    assert len(middleware._tenant_contexts) == 4096
    middleware._keys = LookupOnlyDict(middleware._keys)
    middleware._tenant_contexts = LookupOnlyDict(middleware._tenant_contexts)

    auth.api_keys.clear()
    object.__setattr__(tenancy, "tenants", ())
    response = client.get(
        "/inspect",
        headers={"Authorization": "Bearer secret-4095"},
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == tenant_ids[4095 % len(tenant_ids)]
    assert "secret-4095" not in response.text
    assert middleware._keys.get_calls == 1
    assert middleware._tenant_contexts.get_calls == 1


async def test_concurrent_requests_keep_tenant_context_isolated() -> None:
    """TC-TIC-002: Concurrent requests cannot overwrite tenant Context."""
    auth = AuthConfig(
        enabled=True,
        api_keys=[
            ApiKeyConfig(key="secret-acme", name="acme-app", tenant_id="acme"),
            ApiKeyConfig(
                key="secret-globex",
                name="globex-app",
                tenant_id="globex",
            ),
        ],
    )
    tenancy = TenancyConfig(
        enabled=True,
        tenants=(TenantConfig(id="acme"), TenantConfig(id="globex")),
    )
    app = FastAPI()
    app.add_middleware(AuthMiddleware, config=auth, tenancy=tenancy)
    arrived = 0
    lock = asyncio.Lock()
    both_arrived = asyncio.Event()

    @app.get("/barrier")
    async def barrier(request: Request) -> dict[str, str]:
        nonlocal arrived
        context_before = request.state.tenant_context
        async with lock:
            arrived += 1
            if arrived == 2:
                both_arrived.set()
        await asyncio.wait_for(both_arrived.wait(), timeout=1)
        await asyncio.sleep(0)
        return {
            "before": context_before.tenant_id,
            "after": request.state.tenant_context.tenant_id,
        }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        acme, globex = await asyncio.gather(
            client.get(
                "/barrier",
                headers={"Authorization": "Bearer secret-acme"},
            ),
            client.get(
                "/barrier",
                headers={"Authorization": "Bearer secret-globex"},
            ),
        )

    assert acme.json() == {"before": "acme", "after": "acme"}
    assert globex.json() == {"before": "globex", "after": "globex"}


def test_untrusted_tenant_header_cannot_override_identity() -> None:
    """TC-TIC-003: X-Tenant-ID cannot override the API-key binding."""
    auth, tenancy = _multi_tenant_auth()
    response = TestClient(_tenant_app(auth, tenancy)).get(
        "/inspect",
        headers={
            "Authorization": "Bearer secret-acme",
            "X-Tenant-ID": "globex",
        },
    )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "acme"
    assert response.json()["provider_name"] == "global-provider"
    assert "X-Tenant-ID" not in response.headers
