"""Configuration tests for required detector startup policy."""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.app import _extract_detector_configs
from z_llm_safety_gateway.config.models import DetectorConfig, DetectorsConfig, GatewayConfig
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _gateway_with(detector: DetectorConfig) -> GatewayConfig:
    return GatewayConfig.model_validate(
        {
            "server": {"host": "127.0.0.1", "port": 8080},
            "providers": [
                {
                    "name": "local",
                    "type": "openai_compatible",
                    "base_url": "http://localhost:11434/v1",
                }
            ],
            "routing": {"rules": [{"pattern": "*", "provider": "local"}]},
            "pipeline": {"detectors": {"input": [detector.model_dump()], "output": []}},
        }
    )


def test_required_default_explicit_values_and_extraction() -> None:
    """TC-CFG-601: required defaults false and survives config extraction."""
    assert DetectorConfig(name="prompt_injection").required is False
    explicit_false = DetectorConfig(name="toxicity", required=False)
    configured = DetectorConfig(
        name="prompt_injection",
        required=True,
        on_error="fail_closed",
    )
    extracted = _extract_detector_configs(
        DetectorsConfig(input=[configured, explicit_false]).input,
        default_timeout_seconds=2.0,
    )
    assert extracted["prompt_injection"]["required"] is True
    assert extracted["toxicity"]["required"] is False

    output_extracted = _extract_detector_configs(
        DetectorsConfig(output=[explicit_false]).output,
        default_timeout_seconds=2.0,
    )
    assert output_extracted["toxicity"]["required"] is False


def test_required_fail_open_is_rejected() -> None:
    """TC-CFG-602: required and fail_open is an invalid policy combination."""
    config = _gateway_with(
        DetectorConfig(name="prompt_injection", required=True, on_error="fail_open")
    )

    with pytest.raises(ConfigValidationError, match="required.*fail_closed"):
        validate_config(config)


def test_required_disabled_is_rejected() -> None:
    """TC-CFG-603: a required detector cannot also be disabled."""
    config = _gateway_with(
        DetectorConfig(
            name="prompt_injection",
            required=True,
            enabled=False,
            on_error="fail_closed",
        )
    )

    with pytest.raises(ConfigValidationError, match="required.*disabled"):
        validate_config(config)
