"""Tests for ModelRouter — TC-PROXY-001 through TC-PROXY-004, TC-PROXY-012."""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.models import (
    GatewayConfig,
    ProviderConfig,
    RoutingConfig,
    RoutingRule,
    ServerConfig,
)
from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError
from z_llm_safety_gateway.providers.router import ModelRouter

_OPENAI_PROVIDER = ProviderConfig(
    name="openai",
    type="openai",
    base_url="https://api.openai.com/v1",
    api_key="sk-test-key",
)
_LOCAL_LLAMA_PROVIDER = ProviderConfig(
    name="local_llama",
    type="openai_compatible",
    base_url="http://localhost:11434/v1",
)
_AZURE_PROVIDER = ProviderConfig(
    name="azure",
    type="azure_openai",
    base_url="https://my-resource.openai.azure.com",
    api_key="azure-key",
    api_version="2024-06-01",
)

_ALL_PROVIDERS = [_OPENAI_PROVIDER, _LOCAL_LLAMA_PROVIDER, _AZURE_PROVIDER]


def _make_config(
    rules: list[RoutingRule],
    providers: list[ProviderConfig] | None = None,
) -> GatewayConfig:
    """Create a GatewayConfig with given routing rules and providers."""
    return GatewayConfig(
        server=ServerConfig(),
        providers=providers or _ALL_PROVIDERS,
        routing=RoutingConfig(rules=rules),
    )


class TestModelRouterRouting:
    """Tests for ModelRouter.route() — TC-PROXY-001 through TC-PROXY-004."""

    def test_route_gpt4_matches_first_rule_returns_openai(self) -> None:
        """TC-PROXY-001: model 'gpt-4-turbo' matches 'gpt-4*' and returns openai provider."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="gpt-3.5*", provider="openai"),
                RoutingRule(pattern="azure-*", provider="azure"),
                RoutingRule(pattern="llama*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        provider = router.route("gpt-4-turbo")

        assert isinstance(provider, BaseProvider)
        assert provider.config.name == "openai"

    def test_route_overlapping_patterns_first_match_wins(self) -> None:
        """TC-PROXY-002: overlapping 'gpt-4*' and 'gpt-*', first match 'gpt-4*' wins."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="gpt-*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        provider = router.route("gpt-4-turbo")

        assert provider.config.name == "openai"

    def test_route_llama_matches_llama_pattern_returns_local_llama(self) -> None:
        """TC-PROXY-003: model 'llama3-70b' matches 'llama*' and returns local_llama provider."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="llama*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        provider = router.route("llama3-70b")

        assert provider.config.name == "local_llama"

    def test_route_no_match_raises_provider_error_404(self) -> None:
        """TC-PROXY-004: model 'claude-3-opus' has no matching rule, raises ProviderError 404."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="llama*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        with pytest.raises(ProviderError) as exc_info:
            router.route("claude-3-opus")

        assert exc_info.value.status_code == 404
        assert "claude-3-opus" in exc_info.value.message


class TestModelRouterConflictDetection:
    """Tests for ModelRouter.check_conflicts() — TC-PROXY-012."""

    def test_check_conflicts_overlapping_patterns_returns_warnings(self) -> None:
        """TC-PROXY-012: overlapping 'gpt-4*' and 'gpt-*' produce
        warning, does not block startup."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="gpt-*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        warnings = router.check_conflicts()

        assert len(warnings) >= 1
        combined = " ".join(warnings)
        assert "gpt-4*" in combined
        assert "gpt-*" in combined

    def test_check_conflicts_no_overlap_returns_empty_list(self) -> None:
        """Non-overlapping patterns produce no warnings."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="llama*", provider="local_llama"),
            ],
        )
        router = ModelRouter(config)

        warnings = router.check_conflicts()

        assert len(warnings) == 0

    def test_init_with_conflicts_does_not_raise(self) -> None:
        """Router initializes successfully even with overlapping patterns (no blocking)."""
        config = _make_config(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="gpt-*", provider="local_llama"),
            ],
        )

        router = ModelRouter(config)

        assert router is not None
