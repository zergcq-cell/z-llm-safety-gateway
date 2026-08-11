"""Model-to-provider router using glob pattern matching."""

from __future__ import annotations

import fnmatch

from z_llm_safety_gateway.config.models import GatewayConfig, ProviderConfig
from z_llm_safety_gateway.providers.azure_openai import AzureOpenAIProvider
from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError
from z_llm_safety_gateway.providers.openai import OpenAIProvider
from z_llm_safety_gateway.providers.openai_compatible import OpenAICompatibleProvider

_PROVIDER_TYPES: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "azure_openai": AzureOpenAIProvider,
}


class ModelRouter:
    """Routes model names to providers using glob pattern matching.

    Routing rules are evaluated in YAML declaration order.  The first
    matching pattern wins (``fnmatch`` semantics).  Overlapping patterns
    are detected at construction time and exposed via
    :meth:`check_conflicts` as non-blocking warnings.
    """

    def __init__(self, config: GatewayConfig) -> None:
        self._rules = config.routing.rules
        self._providers: dict[str, ProviderConfig] = {
            p.name: p for p in config.providers
        }
        self._provider_instances: dict[str, BaseProvider] = {}

        timeout = float(config.security.timeout.get("upstream", 120))

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
