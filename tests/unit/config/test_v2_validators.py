"""Tests for v0.2.0 config validator extensions.

Covers: TC-CONF-003~005, TC-CONF-013~015, TC-CONF-017, TC-CONF-019~024.

Tests threshold validation from nested config, flag_escalation rule syntax,
unknown detector names, old list format backward compat, gRPC endpoint
validation, and word_list_file existence checks.
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.models import (
    DetectorConfig,
    DetectorsConfig,
    FlagEscalationConfig,
    GatewayConfig,
    PipelineConfig,
    ProviderConfig,
    RoutingConfig,
    ServerConfig,
)
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


# --------------------------------------------------------------------------- #
# Helper: build a minimal valid GatewayConfig with custom pipeline
# --------------------------------------------------------------------------- #
def _make_config(
    pipeline: PipelineConfig | None = None,
) -> GatewayConfig:
    """Create a GatewayConfig with a custom pipeline for testing."""
    return GatewayConfig(
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
        pipeline=pipeline or PipelineConfig(),
    )


# --------------------------------------------------------------------------- #
# TC-CONF-003 (SC-007): block_threshold < flag_threshold raises error
# --------------------------------------------------------------------------- #
def test_validate_reversed_thresholds_raises_error() -> None:
    """TC-CONF-003 / SC-007: block_threshold=0.50, flag_threshold=0.85 -> error."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="prompt_injection",
                        config={"block_threshold": 0.50, "flag_threshold": 0.85},
                    ),
                ],
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "prompt_injection" in error_msg
    assert "block_threshold" in error_msg
    assert "flag_threshold" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONF-004 (SC-008): block_threshold > flag_threshold accepted
# --------------------------------------------------------------------------- #
def test_validate_valid_thresholds_accepted() -> None:
    """TC-CONF-004 / SC-008: block_threshold=0.85, flag_threshold=0.50 -> OK."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="prompt_injection",
                        config={"block_threshold": 0.85, "flag_threshold": 0.50},
                    ),
                ],
            ),
        )
    )

    # Should not raise
    validate_config(config)


# --------------------------------------------------------------------------- #
# TC-CONF-017 (SC-009): block_threshold == flag_threshold raises error
# --------------------------------------------------------------------------- #
def test_validate_equal_thresholds_raises_error() -> None:
    """TC-CONF-017 / SC-009: equal thresholds rejected."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="toxicity",
                        config={"block_threshold": 0.85, "flag_threshold": 0.85},
                    ),
                ],
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "toxicity" in error_msg
    assert "block_threshold" in error_msg


# --------------------------------------------------------------------------- #
# TC-CONF-005 (SC-017): Unknown detector name raises error
# --------------------------------------------------------------------------- #
def test_validate_unknown_detector_name_raises_error() -> None:
    """TC-CONF-005 / SC-017: 'nonexistent_detector' not built-in and not grpc."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(name="nonexistent_detector"),
                ],
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "nonexistent_detector" in error_msg
    # Should suggest using type: grpc
    assert "grpc" in error_msg.lower()


# --------------------------------------------------------------------------- #
# TC-CONF-021 (SC-018): Known built-in detector name accepted
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "detector_name",
    ["prompt_injection", "pii_redaction", "toxicity", "sensitive_words", "secret_leak"],
)
def test_validate_known_builtin_detector_name_accepted(detector_name: str) -> None:
    """TC-CONF-021 / SC-018: built-in detector names pass validation."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[DetectorConfig(name=detector_name)],
            ),
        )
    )

    # Should not raise
    validate_config(config)


# --------------------------------------------------------------------------- #
# TC-CONF-014 (SC-023): Old list[dict] format auto-converted
# --------------------------------------------------------------------------- #
def test_old_list_format_auto_converted_to_detectors_config() -> None:
    """TC-CONF-014 / SC-023: v0.1.0-style list[dict] detectors auto-converted."""
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
                    "name": "prompt_injection",
                    "type": "keyword",
                    "block_threshold": 0.85,
                    "flag_threshold": 0.50,
                },
            ],
        },
    )

    # After conversion, detectors should be DetectorsConfig with all in input
    assert isinstance(config.pipeline.detectors, DetectorsConfig)
    assert len(config.pipeline.detectors.input) == 1
    assert config.pipeline.detectors.input[0].name == "prompt_injection"
    # Top-level thresholds moved into config dict
    assert config.pipeline.detectors.input[0].config["block_threshold"] == 0.85
    assert config.pipeline.detectors.input[0].config["flag_threshold"] == 0.50
    assert config.pipeline.detectors.output == []

    # Should pass validation (thresholds are valid)
    validate_config(config)


def test_old_list_format_emits_deprecation_warning() -> None:
    """TC-CONF-014 / SC-023: old list format emits deprecation warning."""
    with pytest.warns(UserWarning) as warning_list:
        GatewayConfig(
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
                "detectors": [{"name": "prompt_injection"}],
            },
        )

    deprecation_warnings = [
        w for w in warning_list if "deprecated" in str(w.message).lower()
    ]
    assert len(deprecation_warnings) >= 1


# --------------------------------------------------------------------------- #
# TC-CONF-015 (SC-024): New format parsed directly, no conversion, no warning
# --------------------------------------------------------------------------- #
def test_new_dict_format_parsed_directly_no_warning(
    recwarn: pytest.WarningsRecorder,
) -> None:
    """TC-CONF-015 / SC-024: new {input, output} format parsed without warning."""
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
            "detectors": {
                "input": [{"name": "prompt_injection"}],
                "output": [{"name": "secret_leak"}],
            },
        },
    )

    assert isinstance(config.pipeline.detectors, DetectorsConfig)
    assert len(config.pipeline.detectors.input) == 1
    assert len(config.pipeline.detectors.output) == 1

    # No deprecation warning for new format
    deprecation_warnings = [
        w for w in recwarn.list if "deprecated" in str(w.message).lower()
    ]
    assert len(deprecation_warnings) == 0


# --------------------------------------------------------------------------- #
# TC-CONF-019 (SC-012): flag_escalation.rule valid syntax accepted
# --------------------------------------------------------------------------- #
def test_validate_flag_escalation_valid_rule_accepted() -> None:
    """TC-CONF-019 / SC-012: valid flag_escalation rule passes validation."""
    config = _make_config(
        PipelineConfig(
            flag_escalation=FlagEscalationConfig(
                enabled=True,
                rule="count >= 3 and max_risk_level >= medium",
                action="block",
            ),
        )
    )

    # Should not raise
    validate_config(config)


# --------------------------------------------------------------------------- #
# TC-CONF-011 (SC-013): flag_escalation.rule invalid syntax raises error
# --------------------------------------------------------------------------- #
def test_validate_flag_escalation_invalid_rule_raises_error() -> None:
    """TC-CONF-011 / SC-013: invalid rule syntax 'count >>> 3 and' -> error."""
    config = _make_config(
        PipelineConfig(
            flag_escalation=FlagEscalationConfig(
                enabled=True,
                rule="count >>> 3 and",
                action="block",
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "flag_escalation" in error_msg.lower()


# --------------------------------------------------------------------------- #
# TC-CONF-019 (SC-014): flag_escalation.enabled=false, invalid rule -> no error
# --------------------------------------------------------------------------- #
def test_validate_flag_escalation_disabled_invalid_rule_no_error() -> None:
    """TC-CONF-019 / SC-014: enabled=false, rule not validated."""
    config = _make_config(
        PipelineConfig(
            flag_escalation=FlagEscalationConfig(
                enabled=False,
                rule="invalid syntax >>>",
                action="block",
            ),
        )
    )

    # Should not raise — rule is not validated when disabled
    validate_config(config)


# --------------------------------------------------------------------------- #
# TC-CONF-013 (SC-019): word_list_file missing -> warning
# --------------------------------------------------------------------------- #
def test_validate_word_list_file_missing_emits_warning() -> None:
    """TC-CONF-013 / SC-019: sensitive_words with missing word_list_file warns."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="sensitive_words",
                        config={"word_list_file": "/nonexistent/path/words.txt"},
                    ),
                ],
            ),
        )
    )

    with pytest.warns(UserWarning) as warning_list:
        validate_config(config)

    # At least one warning about the missing file
    file_warnings = [
        w for w in warning_list if "word_list_file" in str(w.message).lower()
        or "missing" in str(w.message).lower()
    ]
    assert len(file_warnings) >= 1


# --------------------------------------------------------------------------- #
# TC-CONF-022 (SC-020): word_list_file exists -> accepted
# --------------------------------------------------------------------------- #
def test_validate_word_list_file_exists_accepted(
    tmp_path: pytest.TempPathFactory,
) -> None:
    """TC-CONF-022 / SC-020: existing word_list_file passes validation."""
    word_file = tmp_path / "words.txt"
    word_file.write_text("spam\nscam\n")

    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="sensitive_words",
                        config={"word_list_file": str(word_file)},
                    ),
                ],
            ),
        )
    )

    # Should not raise
    validate_config(config)


# --------------------------------------------------------------------------- #
# TC-CONF-023 (SC-021): gRPC detector missing endpoint raises error
# --------------------------------------------------------------------------- #
def test_validate_grpc_detector_missing_endpoint_raises_error() -> None:
    """TC-CONF-023 / SC-021: type=grpc without endpoint config -> error."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="commercial_guard",
                        type="grpc",
                        config={"tls_enabled": False},
                    ),
                ],
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "commercial_guard" in error_msg
    assert "endpoint" in error_msg.lower()


# --------------------------------------------------------------------------- #
# TC-CONF-024 (SC-022): gRPC detector without circuit_breaker -> info warning
# --------------------------------------------------------------------------- #
def test_validate_grpc_detector_without_circuit_breaker_emits_info() -> None:
    """TC-CONF-024 / SC-022: gRPC with endpoint but no circuit_breaker -> info."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="commercial_guard",
                        type="grpc",
                        config={"endpoint": "localhost:50051"},
                    ),
                ],
            ),
        )
    )

    with pytest.warns(UserWarning) as warning_list:
        validate_config(config)

    info_warnings = [
        w for w in warning_list if "circuit_breaker" in str(w.message).lower()
    ]
    assert len(info_warnings) >= 1
    assert "commercial_guard" in str(warning_list[0].message)


# --------------------------------------------------------------------------- #
# gRPC detector with endpoint and circuit_breaker -> no warning
# --------------------------------------------------------------------------- #
def test_validate_grpc_detector_with_circuit_breaker_no_warning(
    recwarn: pytest.WarningsRecorder,
) -> None:
    """gRPC detector with endpoint and circuit_breaker -> no info warning."""
    from z_llm_safety_gateway.config.models import CircuitBreakerConfig

    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="commercial_guard",
                        type="grpc",
                        config={"endpoint": "localhost:50051"},
                        circuit_breaker=CircuitBreakerConfig(enabled=True),
                    ),
                ],
            ),
        )
    )

    validate_config(config)

    cb_warnings = [
        w for w in recwarn.list if "circuit_breaker" in str(w.message).lower()
    ]
    assert len(cb_warnings) == 0


# --------------------------------------------------------------------------- #
# Threshold validation in output detectors
# --------------------------------------------------------------------------- #
def test_validate_output_detector_reversed_thresholds_raises_error() -> None:
    """Threshold validation also applies to output detectors."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                output=[
                    DetectorConfig(
                        name="toxicity",
                        config={"block_threshold": 0.50, "flag_threshold": 0.85},
                    ),
                ],
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "toxicity" in error_msg


# --------------------------------------------------------------------------- #
# flag_escalation with 'or' logic and 'contains' operator
# --------------------------------------------------------------------------- #
def test_validate_flag_escalation_with_or_and_contains_accepted() -> None:
    """flag_escalation rule with 'or' and 'categories contains' accepted."""
    config = _make_config(
        PipelineConfig(
            flag_escalation=FlagEscalationConfig(
                enabled=True,
                rule="count >= 3 or categories contains pii",
                action="block",
            ),
        )
    )

    validate_config(config)


# --------------------------------------------------------------------------- #
# flag_escalation with empty rule when enabled
# --------------------------------------------------------------------------- #
def test_validate_flag_escalation_enabled_empty_rule_raises_error() -> None:
    """flag_escalation enabled=True with empty rule -> error."""
    config = _make_config(
        PipelineConfig(
            flag_escalation=FlagEscalationConfig(
                enabled=True,
                rule="",
                action="block",
            ),
        )
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    assert "flag_escalation" in str(exc_info.value).lower()


# --------------------------------------------------------------------------- #
# gRPC detector name not checked against built-in list
# --------------------------------------------------------------------------- #
def test_validate_grpc_detector_with_unknown_name_accepted() -> None:
    """gRPC type detector with non-built-in name is accepted (SC-017 'not type grpc')."""
    config = _make_config(
        PipelineConfig(
            detectors=DetectorsConfig(
                input=[
                    DetectorConfig(
                        name="acme_custom_guard",
                        type="grpc",
                        config={"endpoint": "localhost:50051"},
                        circuit_breaker=None,
                    ),
                ],
            ),
        )
    )

    # Should not raise — gRPC type bypasses built-in name check
    # (will emit info about missing circuit_breaker)
    with pytest.warns(UserWarning):
        validate_config(config)


# --------------------------------------------------------------------------- #
# Old list format with top-level thresholds passes validation
# --------------------------------------------------------------------------- #
def test_old_list_format_with_valid_thresholds_passes_validation() -> None:
    """Old list format with top-level block/flag thresholds converts and passes."""
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
            "detectors": [
                {
                    "name": "prompt_injection",
                    "type": "keyword",
                    "block_threshold": 0.85,
                    "flag_threshold": 0.50,
                },
            ],
        },
    )

    # Should not raise — thresholds are valid after conversion
    validate_config(config)


# --------------------------------------------------------------------------- #
# Old list format with reversed thresholds fails validation
# --------------------------------------------------------------------------- #
def test_old_list_format_with_reversed_thresholds_fails_validation() -> None:
    """Old list format with reversed top-level thresholds fails after conversion."""
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
            "detectors": [
                {
                    "name": "bad_detector",
                    "type": "keyword",
                    "block_threshold": 0.50,
                    "flag_threshold": 0.85,
                },
            ],
        },
    )

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    error_msg = str(exc_info.value)
    assert "bad_detector" in error_msg or "block_threshold" in error_msg
