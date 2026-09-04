"""Trusted tenant policy resolution and middleware contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.config.models import (
    MAX_TENANT_POLICIES,
    MAX_TENANT_POLICY_CAPABILITIES,
    MAX_TENANT_POLICY_ROUTES,
    TenancyConfig,
    TenantPolicyConfig,
)
from z_llm_safety_gateway.middleware.policy_resolution import (
    TenantPolicyResolutionMiddleware,
)
from z_llm_safety_gateway.tenancy import (
    LEGACY_TENANT_CONTEXT,
    TenantContext,
    TenantPolicyUnavailableError,
)
from z_llm_safety_gateway.tenancy.policy import (
    TenantPolicyResolver,
    TenantRuntimeBundle,
)


def _tenancy() -> TenancyConfig:
    return TenancyConfig.model_validate(
        {
            "enabled": True,
            "tenants": [
                {"id": "acme", "policy_id": "strict-policy"},
                {"id": "globex", "policy_id": "research-policy"},
            ],
            "policies": [
                {
                    "id": "strict-policy",
                    "input_flow": {"flow_id": "strict-input", "version": "1.0.0"},
                    "output_flow": None,
                    "routing": {
                        "models_provider": "local",
                        "rules": [{"pattern": "*", "provider": "local"}],
                    },
                },
                {
                    "id": "research-policy",
                    "input_flow": None,
                    "output_flow": {
                        "flow_id": "research-output",
                        "version": "2.0.0",
                    },
                    "routing": {
                        "models_provider": "backup",
                        "rules": [{"pattern": "*", "provider": "backup"}],
                    },
                },
            ],
        }
    )


def _bundle(
    policy_id: str,
    *,
    input_flow: tuple[str, str] | None,
    output_flow: tuple[str, str] | None,
) -> TenantRuntimeBundle:
    return TenantRuntimeBundle(
        policy_id=policy_id,
        input_flow_identity=input_flow,
        output_flow_identity=output_flow,
        routing_profile_id=policy_id,
    )


def _resolver(*, include_research: bool = True) -> TenantPolicyResolver:
    bundles = [
        _bundle(
            "strict-policy",
            input_flow=("strict-input", "1.0.0"),
            output_flow=None,
        )
    ]
    if include_research:
        bundles.append(
            _bundle(
                "research-policy",
                input_flow=None,
                output_flow=("research-output", "2.0.0"),
            )
        )
    return TenantPolicyResolver(_tenancy(), bundles)


def test_trusted_context_selects_safe_frozen_policy_and_private_bundle() -> None:
    """TC-TPR-001: Trusted identities resolve distinct safe contexts and bundles."""
    resolver = _resolver()

    acme = resolver.resolve(TenantContext("acme", "api_key"))
    globex = resolver.resolve(TenantContext("globex", "api_key"))

    assert acme is not None and globex is not None
    assert acme.context.tenant_id == "acme"
    assert acme.context.policy_id == "strict-policy"
    assert acme.context.input_flow_identity == ("strict-input", "1.0.0")
    assert globex.context.policy_id == "research-policy"
    assert globex.context.output_flow_identity == ("research-output", "2.0.0")
    assert acme.bundle is not globex.bundle
    assert acme.context.contract_version == "1.0"
    assert "config" not in repr(acme.context).lower()
    assert "provider" not in repr(acme.context).lower()
    with pytest.raises(FrozenInstanceError):
        acme.context.policy_id = "research-policy"  # type: ignore[misc]


def test_resolution_ignores_untrusted_policy_and_provider_hints() -> None:
    """TC-TPR-002: Only TenantContext participates in policy lookup."""
    resolver = _resolver()
    app = FastAPI()
    app.add_middleware(TenantPolicyResolutionMiddleware, resolver=resolver)

    @app.middleware("http")
    async def inject_trusted_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.tenant_context = TenantContext("acme", "api_key")
        return await call_next(request)

    @app.post("/inspect")
    async def inspect(request: Request) -> dict[str, str]:
        context = request.state.tenant_policy_context
        return {"tenant_id": context.tenant_id, "policy_id": context.policy_id}

    response = TestClient(app).post(
        "/inspect",
        headers={
            "X-Tenant-ID": "globex",
            "X-Policy-ID": "research-policy",
            "X-Provider": "backup",
        },
        json={
            "tenant_id": "globex",
            "policy_id": "research-policy",
            "provider": "backup",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": "acme", "policy_id": "strict-policy"}


@pytest.mark.parametrize("invalid_case", ("missing_context", "unknown_tenant", "missing_bundle"))
def test_runtime_policy_invariants_return_safe_503(invalid_case: str) -> None:
    """TC-TPR-003: Missing runtime policy state fails closed without fallback."""
    resolver = _resolver(include_research=invalid_case != "missing_bundle")
    app = FastAPI()
    app.add_middleware(TenantPolicyResolutionMiddleware, resolver=resolver)

    @app.middleware("http")
    async def inject_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        if invalid_case == "unknown_tenant":
            request.state.tenant_context = TenantContext("unknown", "api_key")
        elif invalid_case == "missing_bundle":
            request.state.tenant_context = TenantContext("globex", "api_key")
        return await call_next(request)

    @app.get("/inspect")
    async def inspect() -> dict[str, bool]:
        return {"unexpected": True}

    response = TestClient(app).get("/inspect")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "message": "Tenant policy is temporarily unavailable",
            "type": "service_unavailable",
            "param": None,
            "code": "tenant_policy_unavailable",
        }
    }
    assert "strict-policy" not in response.text
    assert "research-policy" not in response.text


def test_install_rejects_incomplete_executable_bundle() -> None:
    """TC-TPR-003: startup cannot publish an identity-only runtime bundle."""
    resolver = _resolver()

    with pytest.raises(TenantPolicyUnavailableError, match="tenant_policy_unavailable"):
        resolver.install_bundles(
            [
                _bundle(
                    "strict-policy",
                    input_flow=("strict-input", "1.0.0"),
                    output_flow=None,
                )
            ]
        )


def test_legacy_resolution_preserves_global_runtime_path() -> None:
    """TC-TPR-004: Disabled tenancy returns the existing legacy path marker."""
    resolver = TenantPolicyResolver(TenancyConfig(), ())

    assert resolver.resolve(LEGACY_TENANT_CONTEXT) is None
    assert resolver.enabled is False


def test_policy_resolution_uses_only_precompiled_mapping_lookups() -> None:
    """TC-TPR-006: Request-time policy resolution never scans declarations."""
    tenants = [
        {"id": f"tenant-{index:04d}", "policy_id": f"policy-{index:04d}"}
        for index in range(MAX_TENANT_POLICIES)
    ]
    maximal_policy = TenantPolicyConfig.model_validate(
        {
            "id": "policy-template",
            "input_flow": None,
            "output_flow": None,
            "capabilities": [
                {
                    "capability_id": f"detector.guard-{index:03d}",
                    "detector_name": f"guard-{index:03d}",
                }
                for index in range(MAX_TENANT_POLICY_CAPABILITIES)
            ],
            "routing": {
                "models_provider": "local",
                "rules": [
                    {"pattern": f"model-{index:03d}", "provider": "local"}
                    for index in range(MAX_TENANT_POLICY_ROUTES)
                ],
            },
        }
    )
    policies = [
        maximal_policy.model_copy(update={"id": f"policy-{index:04d}"})
        for index in range(MAX_TENANT_POLICIES)
    ]
    tenancy = TenancyConfig.model_validate(
        {"enabled": True, "tenants": tenants, "policies": policies}
    )
    resolver = TenantPolicyResolver(
        tenancy,
        [
            _bundle(
                f"policy-{index:04d}",
                input_flow=None,
                output_flow=None,
            )
            for index in range(MAX_TENANT_POLICIES)
        ],
    )

    class LookupOnlyDict(dict[str, Any]):
        get_calls = 0

        def get(self, key: str, default: Any = None) -> Any:
            self.get_calls += 1
            return super().get(key, default)

        def __iter__(self):
            raise AssertionError("request-time lookup must not iterate")

        def items(self):
            raise AssertionError("request-time lookup must not scan items")

        def values(self):
            raise AssertionError("request-time lookup must not scan values")

    resolver._tenant_policy_ids = LookupOnlyDict(resolver._tenant_policy_ids)
    resolver._bundles = LookupOnlyDict(resolver._bundles)

    resolved = resolver.resolve(TenantContext("tenant-1023", "api_key"))

    assert resolved is not None
    assert resolved.context.policy_id == "policy-1023"
    assert resolver._tenant_policy_ids.get_calls == 1
    assert resolver._bundles.get_calls == 1
