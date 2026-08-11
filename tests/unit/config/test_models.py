"""Tests for Pydantic v2 config models.

Covers: TC-CONFIG-005~006
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import GatewayConfig


# --------------------------------------------------------------------------- #
# TC-CONFIG-005: Complete valid config dict validates as GatewayConfig
# --------------------------------------------------------------------------- #
def test_gateway_config_valid_dict_validates_successfully() -> None:
    # TC-CONFIG-005
    config_dict = {
        "server": {"host": "0.0.0.0", "port": 8080},
        "providers": [
            {
                "name": "openai",
                "type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test123",
            },
            {
                "name": "local_llama",
                "type": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
            },
            {
                "name": "azure",
                "type": "azure_openai",
                "base_url": "https://my-resource.openai.azure.com",
                "api_key": "sk-azure",
                "api_version": "2024-06-01",
            },
        ],
        "routing": {
            "rules": [
                {"pattern": "gpt-4*", "provider": "openai"},
                {"pattern": "llama*", "provider": "local_llama"},
            ]
        },
        "pipeline": {"mode": "sync", "detectors": []},
        "security": {"timeout": {"upstream": 120}},
        "audit": {"enabled": False, "sanitize_logs": True},
        "observability": {"metrics_enabled": False, "tracing_enabled": False},
    }

    config = GatewayConfig(**config_dict)

    assert isinstance(config, GatewayConfig)
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8080
    assert len(config.providers) == 3
    assert config.providers[0].name == "openai"
    assert config.providers[0].type == "openai"
    assert config.providers[1].name == "local_llama"
    assert config.providers[1].type == "openai_compatible"
    assert config.providers[2].name == "azure"
    assert config.providers[2].api_version == "2024-06-01"
    assert len(config.routing.rules) == 2
    assert config.routing.rules[0].pattern == "gpt-4*"
    assert config.pipeline.mode == "sync"
    assert config.security.timeout["upstream"] == 120
    assert config.audit.sanitize_logs is True
    assert config.observability.metrics_enabled is False

    # Verify defaults are applied when sections are omitted
    minimal_dict = {
        "server": {"host": "127.0.0.1", "port": 9090},
        "providers": [
            {"name": "p1", "type": "openai", "base_url": "http://x", "api_key": "k"},
        ],
        "routing": {"rules": []},
    }
    minimal_config = GatewayConfig(**minimal_dict)
    assert minimal_config.pipeline.mode == "sync"
    assert minimal_config.security.timeout == {"upstream": 120}
    assert minimal_config.audit.enabled is False
    assert minimal_config.observability.tracing_enabled is False


# --------------------------------------------------------------------------- #
# TC-CONFIG-006: server.port as string "not_a_number" raises ValidationError
# --------------------------------------------------------------------------- #
def test_gateway_config_invalid_port_type_raises_validation_error() -> None:
    # TC-CONFIG-006
    config_dict = {
        "server": {"host": "0.0.0.0", "port": "not_a_number"},
        "providers": [
            {"name": "openai", "type": "openai", "base_url": "http://x", "api_key": "k"}
        ],
        "routing": {"rules": []},
    }

    with pytest.raises(ValidationError) as exc_info:
        GatewayConfig(**config_dict)

    error_msg = str(exc_info.value)
    assert "port" in error_msg
    # Error should contain field path information
    assert "server" in error_msg or "port" in error_msg
