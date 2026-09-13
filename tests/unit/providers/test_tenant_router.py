"""Tenant-scoped Provider routing core tests (TC-PROXY-013..017)."""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

from z_llm_safety_gateway.config.models import (
    GatewayConfig,
    ProviderConfig,
    RoutingConfig,
    RoutingRule,
    ServerConfig,
    TenantPolicyRoutingConfig,
    TenantRoutingRuleConfig,
)
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.router import ModelRouter


def _router() -> ModelRouter:
    return ModelRouter(
        GatewayConfig(
            server=ServerConfig(),
            providers=[
                ProviderConfig(
                    name="global-first",
                    type="openai",
                    base_url="https://global.example/v1",
                    api_key="global-secret",
                ),
                ProviderConfig(
                    name="tenant-openai",
                    type="openai",
                    base_url="https://tenant.example/v1",
                    api_key="tenant-secret",
                ),
                ProviderConfig(
                    name="tenant-local",
                    type="openai_compatible",
                    base_url="http://local.invalid/v1",
                ),
                ProviderConfig(
                    name="tenant-gemini",
                    type="gemini",
                    base_url="https://gemini.invalid/v1beta",
                    api_key="gemini-secret",
                ),
            ],
            routing=RoutingConfig(
                rules=[RoutingRule(pattern="*", provider="global-first")]
            ),
        )
    )


def _routing(
    *rules: tuple[str, str], models_provider: str
) -> TenantPolicyRoutingConfig:
    return TenantPolicyRoutingConfig(
        models_provider=models_provider,
        rules=tuple(
            TenantRoutingRuleConfig(pattern=pattern, provider=provider)
            for pattern, provider in rules
        ),
    )


def test_same_model_routes_within_each_tenant_policy() -> None:
    """TC-PROXY-013: identical models resolve independently per tenant view."""
    router = _router()
    acme = router.tenant_view(
        _routing(("shared-*", "tenant-openai"), models_provider="tenant-openai")
    )
    globex = router.tenant_view(
        _routing(("shared-*", "tenant-local"), models_provider="tenant-local")
    )

    assert acme.route("shared-model").config.name == "tenant-openai"
    assert globex.route("shared-model").config.name == "tenant-local"


def test_route_miss_never_falls_back_or_calls_provider() -> None:
    """TC-PROXY-014: a tenant miss is a topology-safe 404 without fallback."""
    router = _router()
    view = router.tenant_view(
        _routing(("allowed-*", "tenant-openai"), models_provider="tenant-openai")
    )
    sensitive_model = "global-only-secret-model"

    with pytest.raises(ProviderError) as exc_info:
        view.route(sensitive_model)

    error = exc_info.value
    assert error.status_code == 404
    assert error.provider_name == "router"
    assert error.message == "No tenant routing rule matches requested model"
    assert sensitive_model not in error.message
    assert "global-first" not in error.message
    assert "global.example" not in error.message


def test_client_hints_cannot_override_tenant_router() -> None:
    """TC-PROXY-015: tenant/provider/policy hints cannot enter core selection."""
    view = _router().tenant_view(
        _routing(("safe-*", "tenant-openai"), models_provider="tenant-openai")
    )

    assert list(inspect.signature(view.route).parameters) == ["model"]
    with pytest.raises(TypeError):
        view.route(  # type: ignore[call-arg]
            "safe-model",
            provider="tenant-local",
            tenant_id="other-tenant",
        )


def test_models_provider_core_preserves_explicit_and_legacy_selection() -> None:
    """TC-PROXY-016: tenant models selection differs from legacy first Provider."""
    router = _router()
    view = router.tenant_view(
        _routing(("safe-*", "tenant-local"), models_provider="tenant-local")
    )

    assert view.models_provider.config.name == "tenant-local"
    assert router.models_provider().config.name == "global-first"


def test_tenant_view_can_isolate_new_provider_types() -> None:
    """TC-ROUTE-001: a tenant view keeps Gemini routing inside its snapshot."""
    router = _router()
    view = router.tenant_view(
        _routing(("gemini-*", "tenant-gemini"), models_provider="tenant-gemini")
    )

    assert view.route("gemini-1.5").config.name == "tenant-gemini"
    with pytest.raises(ProviderError):
        view.route("shared-model")


def test_router_views_reuse_private_provider_instances() -> None:
    """TC-PROXY-017: views share adapters and expose bounded comparisons only."""
    router = _router()
    rules = tuple(
        (f"not-target-{index}", "tenant-openai") for index in range(255)
    ) + (("target-*", "tenant-openai"),)
    first = router.tenant_view(_routing(*rules, models_provider="tenant-openai"))
    second = router.tenant_view(
        _routing(("target-*", "tenant-openai"), models_provider="tenant-openai")
    )

    selection = first.resolve("target-model")

    assert selection.comparisons == 256
    assert selection.provider is second.route("target-model")
    assert first.models_provider is second.models_provider
    assert set(first._provider_instances) == {"tenant-openai"}
    with pytest.raises(FrozenInstanceError):
        first._models_provider_name = "tenant-local"  # type: ignore[misc]
    with pytest.raises(TypeError):
        first._provider_instances["tenant-local"] = second.models_provider  # type: ignore[index]
    rendered = repr(first)
    assert "global-secret" not in rendered
    assert "tenant-secret" not in rendered
    assert "global.example" not in rendered
    assert "tenant.example" not in rendered
    assert "target-*" not in rendered
    assert "tenant-secret" not in repr(selection)

    too_many_rules = rules + (("overflow-*", "tenant-openai"),)
    with pytest.raises(ValueError, match="tenant_policy_route_limit_exceeded"):
        router.tenant_view(
            _routing(*too_many_rules, models_provider="tenant-openai")
        )
