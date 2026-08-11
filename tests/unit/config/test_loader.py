"""Tests for config loader — YAML parsing and environment variable interpolation.

Covers: TC-CONFIG-001~004, TC-CONFIG-016~017
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.loader import (
    _interpolate_env_vars,
    _parse_yaml,
    load_config,
)
from z_llm_safety_gateway.exceptions import ConfigError, ConfigValidationError


# --------------------------------------------------------------------------- #
# TC-CONFIG-001: Valid YAML config file parses into dict with nested structure
# --------------------------------------------------------------------------- #
def test_parse_yaml_valid_config_returns_dict(tmp_path: pytest.TempPathFactory) -> None:
    # TC-CONFIG-001
    yaml_content = """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "sk-test"
  - name: "local_llama"
    type: "openai_compatible"
    base_url: "http://localhost:11434/v1"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"
    - pattern: "llama*"
      provider: "local_llama"

pipeline:
  mode: "sync"
  detectors: []
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    data = _parse_yaml(config_file.read_text())

    assert isinstance(data, dict)
    assert "server" in data
    assert data["server"]["host"] == "127.0.0.1"
    assert data["server"]["port"] == 8080
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert len(data["providers"]) == 2
    assert data["providers"][0]["name"] == "openai"
    assert data["providers"][1]["name"] == "local_llama"
    assert "routing" in data
    assert isinstance(data["routing"]["rules"], list)
    assert len(data["routing"]["rules"]) == 2
    assert data["routing"]["rules"][0]["pattern"] == "gpt-4*"


# --------------------------------------------------------------------------- #
# TC-CONFIG-002: YAML valid but missing providers — parsing succeeds,
#                structural validation deferred to Pydantic
# --------------------------------------------------------------------------- #
def test_parse_yaml_missing_providers_parses_successfully(
    tmp_path: pytest.TempPathFactory,
) -> None:
    # TC-CONFIG-002
    yaml_content = """
server:
  host: "127.0.0.1"
  port: 8080
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    data = _parse_yaml(config_file.read_text())

    # YAML parsing succeeds — no syntax error
    assert isinstance(data, dict)
    assert "server" in data
    assert "providers" not in data

    # Structural validation deferred to Pydantic layer
    with pytest.raises(ConfigValidationError):
        load_config(str(config_file))


# --------------------------------------------------------------------------- #
# TC-CONFIG-003: ${OPENAI_API_KEY} replaced by env var value
# --------------------------------------------------------------------------- #
def test_load_config_with_env_var_interpolation_replaces_value(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # TC-CONFIG-003
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")

    yaml_content = """
server:
  host: "0.0.0.0"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"

routing:
  rules: []
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    config = load_config(str(config_file))

    assert config.providers[0].api_key == "sk-test123"


# --------------------------------------------------------------------------- #
# TC-CONFIG-004: ${UNSET_VAR} resolves to empty string, no exception
# --------------------------------------------------------------------------- #
def test_interpolate_env_vars_unset_var_resolves_to_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # TC-CONFIG-004
    monkeypatch.delenv("UNSET_VAR", raising=False)

    data: dict[str, str] = {"api_key": "${UNSET_VAR}"}
    result = _interpolate_env_vars(data)

    assert result == {"api_key": ""}


# --------------------------------------------------------------------------- #
# TC-CONFIG-016: ${TOTALLY_UNSET_VAR} resolves to empty string, no KeyError
# --------------------------------------------------------------------------- #
def test_interpolate_env_vars_totally_unset_var_no_keyerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # TC-CONFIG-016
    monkeypatch.delenv("TOTALLY_UNSET_VAR", raising=False)

    data: dict[str, str] = {"value": "${TOTALLY_UNSET_VAR}"}
    result = _interpolate_env_vars(data)

    assert result == {"value": ""}


# --------------------------------------------------------------------------- #
# TC-CONFIG-017: Mixed set/unset env vars resolved in single recursive pass
# --------------------------------------------------------------------------- #
def test_interpolate_env_vars_mixed_set_unset_resolved_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # TC-CONFIG-017
    monkeypatch.setenv("SET_VAR", "production")
    monkeypatch.delenv("UNSET_VAR", raising=False)

    data = {
        "set_value": "${SET_VAR}",
        "unset_value": "${UNSET_VAR}",
        "inline": "prefix-${SET_VAR}-suffix",
        "inline_unset": "prefix-${UNSET_VAR}-suffix",
        "nested": {
            "set": "${SET_VAR}",
            "unset": "${UNSET_VAR}",
        },
        "list": ["${SET_VAR}", "${UNSET_VAR}"],
    }
    result = _interpolate_env_vars(data)

    assert result["set_value"] == "production"
    assert result["unset_value"] == ""
    assert result["inline"] == "prefix-production-suffix"
    assert result["inline_unset"] == "prefix--suffix"
    assert result["nested"]["set"] == "production"
    assert result["nested"]["unset"] == ""
    assert result["list"][0] == "production"
    assert result["list"][1] == ""


# --------------------------------------------------------------------------- #
# Helper: verify that a YAML syntax error propagates as ConfigError
# (used by TC-CONFIG-013 in test_validators.py, but also useful here)
# --------------------------------------------------------------------------- #
def test_load_config_file_not_found_raises_config_error() -> None:
    """Loading a non-existent config file raises ConfigError."""
    with pytest.raises(ConfigError):
        load_config("/nonexistent/path/to/config.yaml")
