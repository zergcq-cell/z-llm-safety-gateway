"""Tests for cross-field config validation.

Covers: TC-CONFIG-007~015
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.models import (
    DetectorConfig,
    GatewayConfig,
    ProviderConfig,
    RoutingConfig,
    RoutingRule,
    ServerConfig,
)
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigError, ConfigValidationError


# --------------------------------------------------------------------------- #
# TC-CONFIG-007: block_threshold < flag_threshold raises ValidationError
# --------------------------------------------------------------------------- #
def test_detector_config_reversed_thresholds_raises_error() -> None:
    # TC-CONFIG-007
    with pytest.raises(ValidationError) as exc_info:
        DetectorConfig(
            name="test_detector",
            type="keyword",
            block_threshold=0.50,
            flag_threshold=0.85,
        )

    error_msg = str(exc_info.value)
    assert "test_detector" in error_msg
    assert "0.5" in error_msg
    assert "0.85" in error_msg
    assert "block_threshold" in error_msg
    assert "flag_threshold" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONFIG-008: block_threshold > flag_threshold accepted
# --------------------------------------------------------------------------- #
def test_detector_config_valid_thresholds_accepted() -> None:
    # TC-CONFIG-008
    detector = DetectorConfig(
        name="test_detector",
        type="keyword",
        block_threshold=0.85,
        flag_threshold=0.50,
    )

    assert detector.block_threshold == 0.85
    assert detector.flag_threshold == 0.50


# --------------------------------------------------------------------------- #
# TC-CONFIG-009: block_threshold == flag_threshold raises ValidationError
# --------------------------------------------------------------------------- #
def test_detector_config_equal_thresholds_raises_error() -> None:
    # TC-CONFIG-009
    with pytest.raises(ValidationError) as exc_info:
        DetectorConfig(
            name="test_detector",
            type="keyword",
            block_threshold=0.85,
            flag_threshold=0.85,
        )

    error_msg = str(exc_info.value)
    assert "test_detector" in error_msg
    assert "0.85" in error_msg
    assert "block_threshold" in error_msg
    assert "flag_threshold" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONFIG-010: Overlapping routing patterns produce warning, not error
# --------------------------------------------------------------------------- #
def test_validate_config_overlapping_routing_patterns_warns() -> None:
    # TC-CONFIG-010
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
        routing=RoutingConfig(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="gpt-*", provider="openai"),
            ]
        ),
    )

    with pytest.warns(UserWarning) as warning_list:
        validate_config(config)

    assert len(warning_list) >= 1
    warning_msg = str(warning_list[0].message)
    assert "gpt-4*" in warning_msg
    assert "gpt-*" in warning_msg
    assert "overlap" in warning_msg.lower()


# --------------------------------------------------------------------------- #
# TC-CONFIG-011: Non-overlapping routing patterns produce no warning
# --------------------------------------------------------------------------- #
def test_validate_config_non_overlapping_routing_patterns_no_warning(
    recwarn: pytest.WarningsRecorder,
) -> None:
    # TC-CONFIG-011
    config = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="openai",
                type="openai",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
            ),
            ProviderConfig(
                name="local_llama",
                type="openai_compatible",
                base_url="http://localhost:11434/v1",
            ),
        ],
        routing=RoutingConfig(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="openai"),
                RoutingRule(pattern="llama*", provider="local_llama"),
            ]
        ),
    )

    validate_config(config)

    # No overlap warning should be emitted
    overlap_warnings = [
        w for w in recwarn.list if "overlap" in str(w.message).lower()
    ]
    assert len(overlap_warnings) == 0


# --------------------------------------------------------------------------- #
# TC-CONFIG-012: Pydantic validation failure raises ConfigValidationError
# --------------------------------------------------------------------------- #
def test_load_config_pydantic_validation_failure_raises_config_error(
    tmp_path: pytest.TempPathFactory,
) -> None:
    # TC-CONFIG-012
    yaml_content = """
server:
  host: "0.0.0.0"
  port: "not_a_number"

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "sk-test"

routing:
  rules: []
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(config_file))

    error_msg = str(exc_info.value)
    assert "port" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONFIG-013: YAML syntax error raises error with location info
# --------------------------------------------------------------------------- #
def test_load_config_yaml_syntax_error_raises_error_with_location(
    tmp_path: pytest.TempPathFactory,
) -> None:
    # TC-CONFIG-013
    yaml_content = 'server:\n  host: "127.0.0.1"\n  port: [8080\n'
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    with pytest.raises(ConfigError) as exc_info:
        load_config(str(config_file))

    error_msg = str(exc_info.value)
    # Error message should contain syntax error info and approximate location
    assert "line" in error_msg.lower() or "column" in error_msg.lower()


# --------------------------------------------------------------------------- #
# TC-CONFIG-014: openai provider without api_key raises error with provider name
# --------------------------------------------------------------------------- #
def test_validate_config_openai_provider_missing_api_key_raises_error() -> None:
    # TC-CONFIG-014
    config = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="openai",
                type="openai",
                base_url="https://api.openai.com/v1",
                api_key="",
            ),
        ],
        routing=RoutingConfig(),
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "openai" in error_msg
    assert "api_key" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONFIG-015: openai_compatible without api_key accepted;
#                azure_openai requires api_version
# --------------------------------------------------------------------------- #
def test_validate_config_openai_compatible_without_api_key_accepted() -> None:
    # TC-CONFIG-015
    # Part 1: openai_compatible provider without api_key is accepted
    config_compatible = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="local",
                type="openai_compatible",
                base_url="http://localhost:11434/v1",
            ),
        ],
        routing=RoutingConfig(),
    )

    # Should not raise
    validate_config(config_compatible)

    # Part 2: azure_openai provider without api_version raises error
    config_azure = GatewayConfig(
        server=ServerConfig(),
        providers=[
            ProviderConfig(
                name="azure",
                type="azure_openai",
                base_url="https://my-resource.openai.azure.com",
                api_key="sk-azure",
                api_version="",
            ),
        ],
        routing=RoutingConfig(),
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config_azure)

    error_msg = str(exc_info.value)
    assert "azure" in error_msg
    assert "api_version" in error_msg


# --------------------------------------------------------------------------- #
# Additional: routing rule referencing unknown provider raises error
# --------------------------------------------------------------------------- #
def test_validate_config_routing_rule_unknown_provider_raises_error() -> None:
    """Routing rule referencing a non-existent provider raises ConfigValidationError."""
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
        routing=RoutingConfig(
            rules=[
                RoutingRule(pattern="gpt-4*", provider="nonexistent"),
            ]
        ),
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "nonexistent" in error_msg


# --------------------------------------------------------------------------- #
# Additional: validate_config with detectors in pipeline triggers threshold check
# --------------------------------------------------------------------------- #
def test_validate_config_detector_in_pipeline_invalid_thresholds_raises_error() -> None:
    """Detector configs in pipeline.detectors are validated through validate_config."""
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
        pipeline={
            "mode": "sync",
            "detectors": [
                {
                    "name": "bad_detector",
                    "type": "keyword",
                    "block_threshold": 0.50,
                    "flag_threshold": 0.85,
                }
            ],
        },
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "bad_detector" in error_msg or "block_threshold" in error_msg
