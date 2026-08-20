"""Cross-field validation rules for GatewayConfig.

These validators run after Pydantic model validation and enforce semantic
constraints that span multiple config sections (e.g., routing rules referencing
providers, detector threshold relationships, provider-type-specific requirements).

v0.2.0 additions:
- ``_validate_detectors_v2()``: threshold check from nested ``config`` dict,
  unknown detector name check, gRPC endpoint check, word_list_file existence
  check, and gRPC circuit_breaker info message.
- ``_validate_flag_escalation()``: flag_escalation.rule syntax validation at
  config load time.
"""

from __future__ import annotations

import fnmatch
import os
import re
import warnings

from z_llm_safety_gateway.config.models import (
    DetectorConfig,
    DetectorsConfig,
    GatewayConfig,
)
from z_llm_safety_gateway.exceptions import ConfigValidationError

# Provider types that require a non-empty api_key.
_PROVIDER_TYPES_REQUIRING_API_KEY = frozenset({"openai", "azure_openai"})

# Provider types that require a non-empty api_version.
_PROVIDER_TYPES_REQUIRING_API_VERSION = frozenset({"azure_openai"})

# Test values used to generate sample strings for glob pattern overlap detection.
_OVERLAP_TEST_VALUES = ["", "4", "test", "turbo", "x", "70b", "13b", "-", "mini"]

# Built-in detector names recognised at config validation time.
# Third-party detectors must use ``type: grpc``.
_BUILTIN_DETECTOR_NAMES = frozenset(
    {"prompt_injection", "pii_redaction", "toxicity", "sensitive_words", "secret_leak"}
)

# Variables supported in the flag_escalation rule DSL.
_FLAG_ESCALATION_VARIABLES = frozenset({"count", "max_risk_level", "categories"})

# Operators supported in the flag_escalation rule DSL.
_FLAG_ESCALATION_OPERATORS = frozenset({">=", ">", "<=", "<", "==", "!="})


def validate_config(config: GatewayConfig) -> None:
    """Run all cross-field validation rules on a GatewayConfig.

    Args:
        config: A Pydantic-validated GatewayConfig instance.

    Raises:
        ConfigValidationError: If any cross-field validation rule fails.
    """
    _validate_detectors_v2(config)
    _validate_flag_escalation(config)
    _validate_providers(config)
    _validate_routing(config)


# --------------------------------------------------------------------------- #
# Detector validation (v0.2.0)
# --------------------------------------------------------------------------- #
def _validate_detectors_v2(config: GatewayConfig) -> None:
    """Validate detector configs: thresholds, names, gRPC endpoint, word_list_file.

    Iterates over all detectors in ``pipeline.detectors`` (which is always a
    ``DetectorsConfig`` after the PipelineConfig model_validator conversion).
    For each detector:

    1. **Threshold check**: if both ``block_threshold`` and ``flag_threshold``
       are present in the nested ``config`` dict, verify block > flag.
    2. **Unknown detector name**: if the name is not a built-in detector and
       ``type`` is not ``grpc``, raise an error.
    3. **gRPC endpoint**: if ``type`` is ``grpc``, verify ``endpoint`` is
       present in the ``config`` dict.
    4. **gRPC circuit_breaker info**: if ``type`` is ``grpc`` and no
       circuit_breaker is configured, emit an info-level warning.
    5. **word_list_file**: if the detector is ``sensitive_words`` and
       ``word_list_file`` is specified in ``config``, check file existence
       (warning only, does not block startup).

    Args:
        config: GatewayConfig instance.

    Raises:
        ConfigValidationError: If threshold check, unknown name, or gRPC
            endpoint check fails.
    """
    detectors = config.pipeline.detectors

    # After PipelineConfig model_validator conversion, detectors is always
    # a DetectorsConfig.  Guard for safety against unexpected types.
    if not isinstance(detectors, DetectorsConfig):
        return

    all_detectors: list[tuple[str, DetectorConfig]] = [
        ("input", d) for d in detectors.input
    ] + [
        ("output", d) for d in detectors.output
    ]

    for _direction, detector in all_detectors:
        _validate_required_policy(detector)
        _validate_thresholds(detector)
        _validate_detector_name(detector)
        _validate_grpc_detector(detector)
        _validate_word_list_file(detector)


def _validate_required_policy(detector: DetectorConfig) -> None:
    """Reject contradictory startup requirements before initialization."""
    if not detector.required:
        return
    if not detector.enabled:
        raise ConfigValidationError(
            f"Detector '{detector.name}': required detector cannot be disabled"
        )
    if detector.on_error != "fail_closed":
        raise ConfigValidationError(
            f"Detector '{detector.name}': required detector must use fail_closed"
        )


def _validate_thresholds(detector: DetectorConfig) -> None:
    """Verify confidence and count thresholds independently (v0.4.0).

    Threshold namespace separation (DESIGN 5.3.1):
    - Confidence thresholds: ``block_threshold`` / ``flag_threshold`` (float).
    - Count thresholds: ``count_block_threshold`` / ``count_flag_threshold`` (int).

    Each pair is validated independently: block must be strictly greater than
    flag within its own namespace. This prevents a count-int from being
    misinterpreted as a confidence-float at runtime.

    Args:
        detector: DetectorConfig instance.

    Raises:
        ConfigValidationError: If either threshold pair is invalid.
    """
    cfg = detector.config

    # Confidence thresholds: block_threshold > flag_threshold
    block = cfg.get("block_threshold")
    flag = cfg.get("flag_threshold")
    if block is not None and flag is not None and block <= flag:
        raise ConfigValidationError(
            f"Detector '{detector.name}': block_threshold ({block}) "
            f"must be strictly greater than flag_threshold ({flag})"
        )

    # Count thresholds: count_block_threshold > count_flag_threshold
    count_block = cfg.get("count_block_threshold")
    count_flag = cfg.get("count_flag_threshold")
    if (
        count_block is not None
        and count_flag is not None
        and count_block <= count_flag
    ):
        raise ConfigValidationError(
            f"Detector '{detector.name}': count_block_threshold ({count_block}) "
            f"must be strictly greater than count_flag_threshold ({count_flag})"
        )


def _validate_detector_name(detector: DetectorConfig) -> None:
    """Check that the detector name is a known built-in or has type=grpc.

    v0.5.0: in-process plugin detectors discovered via entry points are also
    accepted.  The error message lists built-in + discovered plugin names and
    a hint for third-party detectors (DESIGN.md Section 10.4, row 2004).

    Args:
        detector: DetectorConfig instance.

    Raises:
        ConfigValidationError: If the name is unknown and type is not grpc.
    """
    # gRPC type bypasses the built-in name check
    if detector.type == "grpc":
        return

    if detector.name in _BUILTIN_DETECTOR_NAMES:
        return

    # v0.5.0: accept detectors discovered from plugin entry points.
    from z_llm_safety_gateway.plugins.loader import discover_plugin_names

    plugin_names = discover_plugin_names()
    if detector.name in plugin_names:
        return

    available = ", ".join(sorted(_BUILTIN_DETECTOR_NAMES | plugin_names))
    raise ConfigValidationError(
        f"Unknown detector '{detector.name}'. "
        f"Available: [{available}]. "
        f"For third-party detectors, ensure the package is installed or use type: grpc."
    )


def _validate_grpc_detector(detector: DetectorConfig) -> None:
    """Validate gRPC detector: endpoint required, circuit_breaker recommended.

    Args:
        detector: DetectorConfig instance.

    Raises:
        ConfigValidationError: If type=grpc and endpoint is missing.
    """
    if detector.type != "grpc":
        return

    endpoint = detector.config.get("endpoint")
    if not endpoint:
        raise ConfigValidationError(
            f"gRPC detector '{detector.name}' is missing required config: endpoint"
        )

    # Info: recommend circuit_breaker for external detectors
    if detector.circuit_breaker is None:
        warnings.warn(
            f"gRPC detector '{detector.name}' has no circuit_breaker configured. "
            f"Recommended for external detectors.",
            UserWarning,
            stacklevel=2,
        )


def _validate_word_list_file(detector: DetectorConfig) -> None:
    """Check that word_list_file exists for sensitive_words detectors.

    Emits a warning (not an error) if the file is missing, as per v0.2.0
    config-system design.

    Args:
        detector: DetectorConfig instance.
    """
    if detector.name != "sensitive_words":
        return

    word_list_file = detector.config.get("word_list_file")
    if not word_list_file:
        return

    if not os.path.isfile(word_list_file):
        warnings.warn(
            f"Detector '{detector.name}' references missing word_list_file: "
            f"{word_list_file}",
            UserWarning,
            stacklevel=2,
        )


# --------------------------------------------------------------------------- #
# Flag escalation validation
# --------------------------------------------------------------------------- #
def _validate_flag_escalation(config: GatewayConfig) -> None:
    """Validate flag_escalation.rule syntax at config load time.

    The rule is only validated when ``flag_escalation.enabled`` is True.
    When disabled, the rule is not parsed (allowing placeholder values).

    Supported DSL syntax:
    - Variables: ``count``, ``max_risk_level``, ``categories``
    - Operators: ``>=``, ``>``, ``<=``, ``<``, ``==``, ``!=``
    - Special: ``categories contains <value>``
    - Logic: ``and``, ``or`` (left-to-right, no parentheses in MVP)

    Args:
        config: GatewayConfig instance.

    Raises:
        ConfigValidationError: If the rule has invalid syntax.
    """
    fe = config.pipeline.flag_escalation
    if fe is None or not fe.enabled:
        return

    rule = fe.rule.strip()
    if not rule:
        raise ConfigValidationError(
            "flag_escalation.rule is empty but flag_escalation is enabled"
        )

    _parse_flag_escalation_rule(rule)


def _parse_flag_escalation_rule(rule: str) -> None:
    """Parse and validate a flag_escalation rule expression.

    Splits the rule by ``and`` / ``or`` keywords (case-insensitive) and
    validates each condition.  A condition is either:
    - ``<variable> <operator> <value>`` (e.g., ``count >= 3``)
    - ``categories contains <value>`` (e.g., ``categories contains pii``)

    Args:
        rule: The rule expression string.

    Raises:
        ConfigValidationError: If any condition has invalid syntax.
    """
    # Split by 'and'/'or' as whole words (case-insensitive)
    parts = re.split(r"\s+(and|or)\s+", rule, flags=re.IGNORECASE)

    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Logic operator — already guaranteed by regex group
            continue

        condition = part.strip()
        if not condition:
            raise ConfigValidationError(
                f"Invalid flag_escalation rule syntax: empty condition in '{rule}'. "
                f"Supported: count, max_risk_level, categories with "
                f">=, >, <=, <, ==, !=, and, or."
            )

        # Check for "categories contains <value>" pattern
        cat_match = re.match(
            r"^categories\s+contains\s+(\S+)$", condition, re.IGNORECASE
        )
        if cat_match:
            continue

        # Check for "<variable> <operator> <value>" pattern
        op_match = re.match(r"^(\w+)\s*(>=|>|<=|<|==|!=)\s*(\S+)$", condition)
        if not op_match:
            raise ConfigValidationError(
                f"Invalid flag_escalation rule syntax: '{condition}'. "
                f"Supported: count, max_risk_level, categories with "
                f">=, >, <=, <, ==, !=, and, or."
            )

        variable = op_match.group(1)
        if variable not in _FLAG_ESCALATION_VARIABLES:
            raise ConfigValidationError(
                f"Invalid flag_escalation variable: '{variable}'. "
                f"Supported variables: count, max_risk_level, categories."
            )


# --------------------------------------------------------------------------- #
# Provider validation (unchanged from v0.1.0)
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Routing validation (unchanged from v0.1.0)
# --------------------------------------------------------------------------- #
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
