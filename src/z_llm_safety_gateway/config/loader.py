"""YAML configuration loader with environment variable interpolation.

Usage:
    from z_llm_safety_gateway.config.loader import load_config
    config = load_config("config.yaml")
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import GatewayConfig
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigError, ConfigValidationError

# Matches ${VAR_NAME} patterns for environment variable interpolation.
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_config(config_path: str) -> GatewayConfig:
    """Load, interpolate, and validate a YAML configuration file.

    Steps:
        1. Read the YAML file from disk.
        2. Parse with yaml.safe_load.
        3. Recursively interpolate ${VAR_NAME} patterns with os.environ values.
        4. Validate via Pydantic v2 GatewayConfig model.
        5. Run cross-field validation (providers, routing, detectors).

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A validated GatewayConfig instance.

    Raises:
        ConfigError: If the file is not found or YAML parsing fails.
        ConfigValidationError: If Pydantic or cross-field validation fails.
    """
    path = Path(config_path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    content = path.read_text()

    try:
        raw_data = _parse_yaml(content)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML syntax error in {config_path}: {exc}") from exc

    interpolated_data = _interpolate_env_vars(raw_data)

    try:
        config = GatewayConfig(**interpolated_data)
    except ValidationError as exc:
        raise ConfigValidationError(f"Config validation failed:\n{exc}") from exc

    validate_config(config)

    return config


def _parse_yaml(content: str) -> dict[str, Any]:
    """Parse a YAML string into a dict using yaml.safe_load.

    Args:
        content: YAML string to parse.

    Returns:
        Parsed dictionary. Returns an empty dict for empty/None content.

    Raises:
        yaml.YAMLError: If the YAML has syntax errors.
        ConfigError: If the top-level YAML element is not a mapping.
    """
    data = yaml.safe_load(content)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file must contain a YAML mapping (dict) at the top level, "
            f"got {type(data).__name__}"
        )
    return data


def _interpolate_env_vars(data: Any) -> Any:
    """Recursively replace ${VAR_NAME} patterns with environment variable values.

    Traverses dicts, lists, and strings. Unset variables resolve to an empty
    string (using os.environ.get semantics) rather than raising.

    Args:
        data: Any parsed YAML data structure (dict, list, str, int, etc.).

    Returns:
        A copy of the data with all ${VAR_NAME} patterns replaced.
    """
    if isinstance(data, dict):
        return {key: _interpolate_env_vars(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_interpolate_env_vars(item) for item in data]
    if isinstance(data, str):
        return _ENV_VAR_PATTERN.sub(
            lambda match: os.environ.get(match.group(1), ""),
            data,
        )
    return data
