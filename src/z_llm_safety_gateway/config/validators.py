"""Cross-field validation rules for GatewayConfig.

These validators run after Pydantic model validation and enforce semantic
constraints that span multiple config sections (e.g., routing rules referencing
providers, detector threshold relationships, provider-type-specific requirements).
"""

from __future__ import annotations

import fnmatch
import warnings

from pydantic import ValidationError

from z_llm_safety_gateway.config.models import DetectorConfig, GatewayConfig
from z_llm_safety_gateway.exceptions import ConfigValidationError

# Provider types that require a non-empty api_key.
_PROVIDER_TYPES_REQUIRING_API_KEY = frozenset({"openai", "azure_openai"})

# Provider types that require a non-empty api_version.
_PROVIDER_TYPES_REQUIRING_API_VERSION = frozenset({"azure_openai"})

# Test values used to generate sample strings for glob pattern overlap detection.
_OVERLAP_TEST_VALUES = ["", "4", "test", "turbo", "x", "70b", "13b", "-", "mini"]


def validate_config(config: GatewayConfig) -> None:
    """Run all cross-field validation rules on a GatewayConfig.

    Args:
        config: A Pydantic-validated GatewayConfig instance.

    Raises:
        ConfigValidationError: If any cross-field validation rule fails.
    """
    _validate_detectors(config)
    _validate_providers(config)
    _validate_routing(config)


def _validate_detectors(config: GatewayConfig) -> None:
    """Validate detector configs by instantiating DetectorConfig from dicts.

    The pipeline.detectors field stores raw dicts; this function converts each
    to a DetectorConfig to trigger the threshold model_validator.

    Args:
        config: GatewayConfig instance.

    Raises:
        ConfigValidationError: If any detector fails validation.
    """
    for detector_dict in config.pipeline.detectors:
        try:
            DetectorConfig(**detector_dict)
        except ValidationError as exc:
            raise ConfigValidationError(
                f"Detector validation failed:\n{exc}"
            ) from exc


def _validate_providers(config: GatewayConfig) -> None:
    """Validate provider-type-specific required fields.

    Rules:
    - openai and azure_openai providers require a non-empty api_key.
    - azure_openai providers also require a non-empty api_version.
    - openai_compatible providers do not require api_key.

    Args:
        config: GatewayConfig instance.

    Raises:
        ConfigValidationError: If a provider is missing a required field.
    """
    for provider in config.providers:
        if provider.type in _PROVIDER_TYPES_REQUIRING_API_KEY and not provider.api_key:
            raise ConfigValidationError(
                f"Provider '{provider.name}': api_key is required for "
                f"provider type '{provider.type}'"
            )
        if (
            provider.type in _PROVIDER_TYPES_REQUIRING_API_VERSION
            and not provider.api_version
        ):
            raise ConfigValidationError(
                f"Provider '{provider.name}': api_version is required for "
                f"provider type '{provider.type}'"
            )


def _validate_routing(config: GatewayConfig) -> None:
    """Validate routing rules: provider existence and pattern conflicts.

    Args:
        config: GatewayConfig instance.

    Raises:
        ConfigValidationError: If a routing rule references an unknown provider.
    """
    provider_names = {p.name for p in config.providers}

    for rule in config.routing.rules:
        if rule.provider not in provider_names:
            raise ConfigValidationError(
                f"Routing rule '{rule.pattern}' references unknown "
                f"provider '{rule.provider}'"
            )

    _check_routing_conflicts(config)


def _check_routing_conflicts(config: GatewayConfig) -> None:
    """Detect overlapping glob patterns in routing rules and emit warnings.

    Two patterns overlap if there exists a model name that matches both.
    The first matching rule in YAML order wins at runtime; a warning is emitted
    but startup is not blocked.

    Args:
        config: GatewayConfig instance.
    """
    rules = config.routing.rules
    for i, rule_i in enumerate(rules):
        for j in range(i + 1, len(rules)):
            rule_j = rules[j]
            if _patterns_overlap(rule_i.pattern, rule_j.pattern):
                warnings.warn(
                    f"Routing patterns '{rule_i.pattern}' and '{rule_j.pattern}' "
                    f"overlap; rule '{rule_i.pattern}' (first in YAML order) "
                    f"takes precedence",
                    stacklevel=2,
                )


def _patterns_overlap(pattern1: str, pattern2: str) -> bool:
    """Check if two glob patterns could match the same string.

    Uses a two-pronged approach:
    1. Check if one pattern (as a literal string) matches the other pattern (as a glob).
    2. Generate sample strings from each pattern and test against the other.

    This is a heuristic and may produce false negatives for complex patterns,
    but is sufficient for common routing patterns (prefix-style like 'gpt-4*').

    Args:
        pattern1: First glob pattern.
        pattern2: Second glob pattern.

    Returns:
        True if the patterns could match at least one common string.
    """
    # Approach 1: treat one pattern as a literal string and match against the other
    if fnmatch.fnmatch(pattern1, pattern2):
        return True
    if fnmatch.fnmatch(pattern2, pattern1):
        return True

    # Approach 2: generate sample strings and cross-check
    for value in _OVERLAP_TEST_VALUES:
        sample1 = pattern1.replace("*", value)
        if fnmatch.fnmatch(sample1, pattern2):
            return True
        sample2 = pattern2.replace("*", value)
        if fnmatch.fnmatch(sample2, pattern1):
            return True

    return False
