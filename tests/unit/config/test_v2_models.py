"""Tests for v0.2.0 config model refactor.

Covers: TC-CONF-001, TC-CONF-002, TC-CONF-006~012, TC-CONF-016, TC-CONF-018.

Tests the new DetectorsConfig bidirectional grouping, DetectorConfig extended
fields, nested config block for thresholds, PipelineConfig extensions,
FlagEscalationConfig, CircuitBreakerConfig, and ModelCacheConfig.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import (
    CircuitBreakerConfig,
    DetectorConfig,
    DetectorsConfig,
    FlagEscalationConfig,
    GatewayConfig,
    ModelCacheConfig,
    PipelineConfig,
    ProviderConfig,
    RoutingConfig,
    ServerConfig,
)


# --------------------------------------------------------------------------- #
# TC-CONF-001: DetectorsConfig bidirectional grouping (input/output)
# --------------------------------------------------------------------------- #
def test_detectors_config_bidirectional_grouping_parses_input_and_output() -> None:
    """TC-CONF-001 / SC-001: detectors with input and output lists parse into
    DetectorsConfig with both fields as list[DetectorConfig]."""
    detectors = DetectorsConfig(
        input=[
            {"name": "prompt_injection", "type": "", "config": {"block_threshold": 0.85}},
            {"name": "pii_redaction", "type": ""},
        ],
        output=[
            {"name": "toxicity", "type": ""},
        ],
    )

    assert len(detectors.input) == 2
    assert len(detectors.output) == 1
    assert isinstance(detectors.input[0], DetectorConfig)
    assert detectors.input[0].name == "prompt_injection"
    assert detectors.output[0].name == "toxicity"


def test_detectors_config_empty_input_and_output_is_valid() -> None:
    """TC-CONF-001 / SC-001: empty input or output list is valid."""
    detectors = DetectorsConfig()

    assert detectors.input == []
    assert detectors.output == []


# --------------------------------------------------------------------------- #
# TC-CONF-006: Only input list, no output -> output defaults to empty
# --------------------------------------------------------------------------- #
def test_detectors_config_only_input_output_defaults_empty() -> None:
    """TC-CONF-006 / SC-002: dict with only input and no output accepted."""
    detectors = DetectorsConfig(
        input=[{"name": "prompt_injection"}],
    )

    assert len(detectors.input) == 1
    assert detectors.output == []


# --------------------------------------------------------------------------- #
# TC-CONF-002: DetectorConfig extended fields
# --------------------------------------------------------------------------- #
def test_detector_config_extended_fields_parsed() -> None:
    """TC-CONF-002 / SC-003: DetectorConfig with all extended fields."""
    detector = DetectorConfig(
        name="pii_redaction",
        type="",
        enabled=True,
        priority=10,
        on_error="fail_closed",
        circuit_breaker=CircuitBreakerConfig(
            enabled=True,
            failure_threshold=5,
            recovery_timeout="30s",
            fallback_action="fail_open",
        ),
        config={"entity_types": ["email", "phone"], "redaction_mode": "mask"},
        timeout="10s",
    )

    assert detector.name == "pii_redaction"
    assert detector.enabled is True
    assert detector.priority == 10
    assert detector.on_error == "fail_closed"
    assert detector.circuit_breaker is not None
    assert detector.circuit_breaker.failure_threshold == 5
    assert detector.config["entity_types"] == ["email", "phone"]
    assert detector.timeout == "10s"


def test_detector_config_default_values() -> None:
    """TC-CONF-002 / SC-003: defaults for priority, on_error, circuit_breaker, config."""
    detector = DetectorConfig(name="test_detector")

    assert detector.type == ""
    assert detector.enabled is True
    assert detector.priority == 100
    assert detector.on_error == "fail_open"
    assert detector.circuit_breaker is None
    assert detector.config == {}
    assert detector.timeout is None


# --------------------------------------------------------------------------- #
# TC-CONF-007 (SC-004): Invalid on_error value raises ValidationError
# --------------------------------------------------------------------------- #
def test_detector_config_invalid_on_error_raises_error() -> None:
    """TC-CONF-007 / SC-004: on_error='fail_silently' raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        DetectorConfig(name="test", on_error="fail_silently")

    error_msg = str(exc_info.value)
    assert "on_error" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONF-008 (SC-005): block_threshold/flag_threshold in nested config block
# --------------------------------------------------------------------------- #
def test_detector_config_thresholds_in_nested_config_block() -> None:
    """TC-CONF-008 / SC-005: thresholds parsed from config dict, not top-level."""
    detector = DetectorConfig(
        name="prompt_injection",
        config={"block_threshold": 0.85, "flag_threshold": 0.50},
    )

    # Thresholds are inside config dict, not top-level fields
    assert detector.config["block_threshold"] == 0.85
    assert detector.config["flag_threshold"] == 0.50
    # DetectorConfig shall NOT have block_threshold/flag_threshold as direct fields
    assert not hasattr(detector, "block_threshold")
    assert not hasattr(detector, "flag_threshold")


# --------------------------------------------------------------------------- #
# TC-CONF-016 (SC-006): Non-threshold detector doesn't require thresholds
# --------------------------------------------------------------------------- #
def test_detector_config_non_threshold_detector_no_thresholds_required() -> None:
    """TC-CONF-016 / SC-006: sensitive_words detector without thresholds valid."""
    detector = DetectorConfig(
        name="sensitive_words",
        config={"word_list_file": "config/wordlists/sensitive_en.txt"},
    )

    assert "block_threshold" not in detector.config
    assert "flag_threshold" not in detector.config


# --------------------------------------------------------------------------- #
# TC-CONF-009 (SC-010): PipelineConfig extended fields
# --------------------------------------------------------------------------- #
def test_pipeline_config_extended_fields_parsed() -> None:
    """TC-CONF-009 / SC-010: PipelineConfig with short_circuit_on, flag_escalation,
    sync_timeout."""
    pipeline = PipelineConfig(
        mode="sync",
        execution_mode="parallel",
        short_circuit_on="block_and_modify",
        sync_timeout="10s",
        flag_escalation=FlagEscalationConfig(
            enabled=True,
            rule="count >= 3 and max_risk_level >= medium",
            action="block",
        ),
    )

    assert pipeline.mode == "sync"
    assert pipeline.execution_mode == "parallel"
    assert pipeline.short_circuit_on == "block_and_modify"
    assert pipeline.sync_timeout == "10s"
    assert pipeline.flag_escalation is not None
    assert pipeline.flag_escalation.enabled is True
    assert pipeline.flag_escalation.rule == "count >= 3 and max_risk_level >= medium"
    assert pipeline.flag_escalation.action == "block"


def test_pipeline_config_default_values() -> None:
    """TC-CONF-009 / SC-010: PipelineConfig defaults."""
    pipeline = PipelineConfig()

    assert pipeline.mode == "sync"
    assert pipeline.execution_mode == "parallel"
    assert pipeline.short_circuit_on == "block"
    assert pipeline.sync_timeout == "5s"
    assert pipeline.flag_escalation is None
    assert isinstance(pipeline.detectors, DetectorsConfig)


# --------------------------------------------------------------------------- #
# TC-CONF-018 (SC-011): Invalid short_circuit_on raises ValidationError
# --------------------------------------------------------------------------- #
def test_pipeline_config_invalid_short_circuit_on_raises_error() -> None:
    """TC-CONF-018 / SC-011: short_circuit_on='block_and_flag' raises error."""
    with pytest.raises(ValidationError) as exc_info:
        PipelineConfig(short_circuit_on="block_and_flag")

    error_msg = str(exc_info.value)
    assert "short_circuit_on" in error_msg


# --------------------------------------------------------------------------- #
# FlagEscalationConfig
# --------------------------------------------------------------------------- #
def test_flag_escalation_config_defaults() -> None:
    """FlagEscalationConfig default values."""
    fe = FlagEscalationConfig()

    assert fe.enabled is False
    assert fe.rule == ""
    assert fe.action == "block"


def test_flag_escalation_config_with_rule() -> None:
    """FlagEscalationConfig with rule."""
    fe = FlagEscalationConfig(
        enabled=True,
        rule="count >= 3 and max_risk_level >= medium",
        action="block",
    )

    assert fe.enabled is True
    assert "count" in fe.rule


# --------------------------------------------------------------------------- #
# CircuitBreakerConfig
# --------------------------------------------------------------------------- #
def test_circuit_breaker_config_defaults() -> None:
    """CircuitBreakerConfig default values."""
    cb = CircuitBreakerConfig()

    assert cb.enabled is False
    assert cb.failure_threshold == 5
    assert cb.recovery_timeout == "30s"
    assert cb.fallback_action == "fail_open"


def test_circuit_breaker_config_custom_values() -> None:
    """CircuitBreakerConfig with custom values."""
    cb = CircuitBreakerConfig(
        enabled=True,
        failure_threshold=10,
        recovery_timeout="60s",
        fallback_action="fail_closed",
    )

    assert cb.enabled is True
    assert cb.failure_threshold == 10
    assert cb.recovery_timeout == "60s"
    assert cb.fallback_action == "fail_closed"


# --------------------------------------------------------------------------- #
# TC-CONF-012 (SC-015): ModelCacheConfig
# --------------------------------------------------------------------------- #
def test_model_cache_config_defaults() -> None:
    """TC-CONF-012 / SC-015: ModelCacheConfig default values."""
    mc = ModelCacheConfig()

    assert mc.dir == "~/.cache/z_llm_safety_gateway/models/"
    assert mc.offline_mode is False


def test_model_cache_config_custom_values() -> None:
    """TC-CONF-012 / SC-015: ModelCacheConfig with custom values."""
    mc = ModelCacheConfig(dir="/app/models", offline_mode=True)

    assert mc.dir == "/app/models"
    assert mc.offline_mode is True


# --------------------------------------------------------------------------- #
# GatewayConfig with model_cache
# --------------------------------------------------------------------------- #
def test_gateway_config_includes_model_cache_field() -> None:
    """GatewayConfig has model_cache field with ModelCacheConfig default."""
    config = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="openai",
                type="openai",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
            ),
        ],
        routing=RoutingConfig(),
    )

    assert isinstance(config.model_cache, ModelCacheConfig)
    assert config.model_cache.dir == "~/.cache/z_llm_safety_gateway/models/"
    assert config.model_cache.offline_mode is False


def test_gateway_config_model_cache_custom_values() -> None:
    """GatewayConfig accepts custom model_cache values."""
    config = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="openai",
                type="openai",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
            ),
        ],
        routing=RoutingConfig(),
        model_cache={"dir": "/data/models", "offline_mode": True},
    )

    assert config.model_cache.dir == "/data/models"
    assert config.model_cache.offline_mode is True


# --------------------------------------------------------------------------- #
# DetectorConfig in DetectorsConfig via dict (as parsed from YAML)
# --------------------------------------------------------------------------- #
def test_detectors_config_from_dict_with_nested_config() -> None:
    """DetectorsConfig accepts dict input with nested config blocks."""
    detectors = DetectorsConfig.model_validate(
        {
            "input": [
                {
                    "name": "prompt_injection",
                    "enabled": True,
                    "priority": 100,
                    "config": {
                        "block_threshold": 0.85,
                        "flag_threshold": 0.50,
                    },
                    "on_error": "fail_open",
                },
            ],
            "output": [
                {
                    "name": "secret_leak",
                    "enabled": True,
                    "priority": 10,
                    "config": {"patterns": ["api_key", "private_key"]},
                    "on_error": "fail_closed",
                },
            ],
        }
    )

    assert len(detectors.input) == 1
    assert detectors.input[0].name == "prompt_injection"
    assert detectors.input[0].config["block_threshold"] == 0.85
    assert detectors.input[0].on_error == "fail_open"
    assert len(detectors.output) == 1
    assert detectors.output[0].name == "secret_leak"
    assert detectors.output[0].on_error == "fail_closed"


# --------------------------------------------------------------------------- #
# CircuitBreakerConfig invalid fallback_action
# --------------------------------------------------------------------------- #
def test_circuit_breaker_config_invalid_fallback_action_raises_error() -> None:
    """CircuitBreakerConfig with invalid fallback_action raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        CircuitBreakerConfig(fallback_action="fail_silently")

    error_msg = str(exc_info.value)
    assert "fallback_action" in error_msg
