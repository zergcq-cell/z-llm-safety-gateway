"""Model-to-provider router using glob pattern matching."""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from z_llm_safety_gateway.config.models import (
    MAX_TENANT_POLICY_ROUTES,
    GatewayConfig,
    ProviderConfig,
    TenantPolicyRoutingConfig,
    TenantRoutingRuleConfig,
)
from z_llm_safety_gateway.providers.anthropic import AnthropicProvider
from z_llm_safety_gateway.providers.azure_openai import AzureOpenAIProvider
from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError
from z_llm_safety_gateway.providers.gemini import GeminiProvider
from z_llm_safety_gateway.providers.openai import OpenAIProvider
from z_llm_safety_gateway.providers.openai_compatible import OpenAICompatibleProvider

_PROVIDER_TYPES: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "azure_openai": AzureOpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


@dataclass(frozen=True, slots=True)
class TenantRouteSelection:
    """One tenant-scoped route decision with bounded-work evidence."""

    provider: BaseProvider = field(repr=False)
    comparisons: int


@dataclass(frozen=True, slots=True, repr=False)
class TenantRouterView:
    """Immutable tenant routing rules over shared Provider adapters."""

    _rules: tuple[TenantRoutingRuleConfig, ...] = field(repr=False)
    _provider_instances: Mapping[str, BaseProvider] = field(repr=False)
    _models_provider_name: str = field(repr=False)

    def __repr__(self) -> str:
        """Return a bounded representation without routing or Provider details."""
        return f"TenantRouterView(rule_count={len(self._rules)})"

    @property
    def models_provider(self) -> BaseProvider:
        """Return the policy's explicit Provider for ``GET /v1/models``."""
        return self._provider_instances[self._models_provider_name]

    def resolve(self, model: str) -> TenantRouteSelection:
        """Resolve *model* and expose the deterministic comparison count."""
        for comparisons, rule in enumerate(self._rules, start=1):
            if fnmatch.fnmatch(model, rule.pattern):
                return TenantRouteSelection(
                    provider=self._provider_instances[rule.provider],
                    comparisons=comparisons,
                )

        raise ProviderError(
            provider_name="router",
            message="No tenant routing rule matches requested model",
            status_code=404,
        )

    def route(self, model: str) -> BaseProvider:
        """Route *model* strictly inside this tenant policy's rule domain."""
        return self.resolve(model).provider


class ModelRouter:
    """Routes model names to providers using glob pattern matching.

    Routing rules are evaluated in YAML declaration order.  The first
    matching pattern wins (``fnmatch`` semantics).  Overlapping patterns
    are detected at construction time and exposed via
    :meth:`check_conflicts` as non-blocking warnings.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self._rules = config.routing.rules
        self._legacy_models_provider_name = (
            config.providers[0].name if config.providers else None
        )
        self._providers: dict[str, ProviderConfig] = {
            p.name: p for p in config.providers
        }
        self._provider_instances: dict[str, BaseProvider] = {}

        timeout = config.security.timeout.upstream_seconds

        for name, provider_config in self._providers.items():
            provider_cls = _PROVIDER_TYPES.get(provider_config.type)
            if provider_cls is None:
                raise ValueError(
                    f"Unknown provider type '{provider_config.type}' "
                    f"for provider '{name}'"
                )
            self._provider_instances[name] = provider_cls(
                provider_config, timeout=timeout
            )

        self._conflict_warnings = self._detect_conflicts()

    def tenant_view(self, routing: TenantPolicyRoutingConfig) -> TenantRouterView:
        """Compile an immutable tenant view that reuses initialized adapters.

        The view receives only adapters named by its rules. This prevents a
        later request-time lookup from reaching a Provider outside the captured
        tenant policy, while keeping adapter construction global and one-time.
        """
        rules = tuple(routing.rules)
        if len(rules) > MAX_TENANT_POLICY_ROUTES:
            raise ValueError("tenant_policy_route_limit_exceeded")

        allowed_provider_names: set[str] = set()
        providers_by_pattern: dict[str, str] = {}
        for rule in rules:
            previous_provider = providers_by_pattern.get(rule.pattern)
            if previous_provider is not None and previous_provider != rule.provider:
                raise ValueError("tenant_policy_route_conflict")
            providers_by_pattern[rule.pattern] = rule.provider

            if rule.provider not in self._provider_instances:
                raise ValueError("tenant_policy_route_provider_not_found")
            allowed_provider_names.add(rule.provider)

        if routing.models_provider not in self._provider_instances:
            raise ValueError("tenant_policy_route_provider_not_found")
        if routing.models_provider not in allowed_provider_names:
            raise ValueError("tenant_policy_models_provider_not_allowed")

        shared_allowed_instances = MappingProxyType(
            {
                name: self._provider_instances[name]
                for name in allowed_provider_names
            }
        )
        return TenantRouterView(
            _rules=rules,
            _provider_instances=shared_allowed_instances,
            _models_provider_name=routing.models_provider,
        )

    def models_provider(self) -> BaseProvider:
        """Return the first configured Provider for legacy ``GET /v1/models``."""
        if self._legacy_models_provider_name is None:
            raise ProviderError(
                provider_name="router",
                message="No providers configured",
                status_code=500,
            )
        return self._provider_instances[self._legacy_models_provider_name]

    def route(self, model: str) -> BaseProvider:
        """Route *model* to the first matching provider (first match wins).

        Raises:
            ProviderError: With ``status_code=404`` when no routing rule
                matches the given model name.
        """
        for rule in self._rules:
            if fnmatch.fnmatch(model, rule.pattern):
                provider = self._provider_instances.get(rule.provider)
                if provider is None:
                    raise ProviderError(
                        provider_name=rule.provider,
                        message=(
                            f"Routing rule references unknown provider "
                            f"'{rule.provider}'"
                        ),
                        status_code=500,
                    )
                return provider

        raise ProviderError(
            provider_name="router",
            message=f"No routing rule matches model '{model}'",
            status_code=404,
        )

    def check_conflicts(self) -> list[str]:
        """Return a list of warning strings for overlapping glob patterns.

        This method does not block startup; it is informational only.
        """
        return list(self._conflict_warnings)

    def _detect_conflicts(self) -> list[str]:
        """Detect overlapping routing patterns and build warning messages."""
        warnings: list[str] = []
        rules = self._rules

        for i, rule_i in enumerate(rules):
            for j in range(i + 1, len(rules)):
                rule_j = rules[j]
                # Heuristic: two patterns overlap if one pattern matches the
                # other when treated as a model name (or vice-versa).
                if fnmatch.fnmatch(rule_i.pattern, rule_j.pattern) or fnmatch.fnmatch(
                    rule_j.pattern, rule_i.pattern
                ):
                    warnings.append(
                        f"Routing conflict: pattern '{rule_i.pattern}' "
                        f"(rule #{i}, provider: {rule_i.provider}) overlaps "
                        f"with '{rule_j.pattern}' (rule #{j}, provider: "
                        f"{rule_j.provider}). First match '{rule_i.pattern}' "
                        f"takes precedence."
                    )

        return warnings
