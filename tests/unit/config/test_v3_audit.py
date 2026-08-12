"""Unit tests for v0.3.0 audit / logging config models.

Covers TC-CONF-007 through TC-CONF-009 (config-system spec).
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _build_yaml(audit: dict | None = None, logging: dict | None = None) -> str:
    """Build a minimal valid config YAML with optional audit/logging sections."""
    import yaml

    config = {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "openai",
                "type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
            }
        ],
        "routing": {"rules": [{"pattern": "gpt-4*", "provider": "openai"}]},
        "pipeline": {},
    }
    if audit is not None:
        config["audit"] = audit
    if logging is not None:
        config["logging"] = logging
    return yaml.safe_dump(config)


# --------------------------------------------------------------------------- #
# TC-CONF-007: AuditConfig extension parsing
# --------------------------------------------------------------------------- #
def test_audit_config_full_parse(tmp_path):
    """TC-CONF-007: extended audit config parses with file/stdout/store_content."""
    yaml_str = _build_yaml(
        audit={
            "enabled": True,
            "store_content": False,
            "sanitize_logs": True,
            "file": {
                "enabled": True,
                "path": "/var/log/safety-gateway",
                "rotation": "daily",
                "retention_days": 90,
            },
            "stdout": True,
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    assert cfg.audit.enabled is True
    assert cfg.audit.store_content is False
    assert cfg.audit.sanitize_logs is True
    assert cfg.audit.file is not None
    assert cfg.audit.file.enabled is True
    assert cfg.audit.file.path == "/var/log/safety-gateway"
    assert cfg.audit.file.rotation == "daily"
    assert cfg.audit.file.retention_days == 90
    assert cfg.audit.stdout is True


def test_audit_config_defaults(tmp_path):
    """TC-CONF-007b: absent audit section uses defaults."""
    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    assert cfg.audit.enabled is False
    assert cfg.audit.store_content is False
    assert cfg.audit.sanitize_logs is True
    assert cfg.audit.stdout is True


# --------------------------------------------------------------------------- #
# TC-CONF-008: rotation value accepted as string (no startup error)
# --------------------------------------------------------------------------- #
def test_audit_rotation_any_string_accepted(tmp_path):
    """TC-CONF-008: rotation accepts arbitrary string (handler validates)."""
    yaml_str = _build_yaml(audit={"file": {"rotation": "hourly"}})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    # Should not raise — rotation validated by logging handler
    cfg = load_config(str(cfg_path))
    assert cfg.audit.file.rotation == "hourly"


# --------------------------------------------------------------------------- #
# TC-CONF-009: LoggingConfig parsing + defaults
# --------------------------------------------------------------------------- #
def test_logging_config_parse(tmp_path):
    """TC-CONF-009: logging section parses level/format."""
    yaml_str = _build_yaml(logging={"level": "DEBUG", "format": "json"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    assert cfg.logging.level == "DEBUG"
    assert cfg.logging.format == "json"


def test_logging_config_defaults(tmp_path):
    """TC-CONF-009b: absent logging section uses defaults."""
    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    assert cfg.logging.level == "INFO"
    assert cfg.logging.format == "json"


def test_logging_config_invalid_level(tmp_path):
    """TC-CONF-009c: invalid logging.level raises validation error."""
    yaml_str = _build_yaml(logging={"level": "TRACE"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    with pytest.raises(ConfigValidationError):
        load_config(str(cfg_path))


# --------------------------------------------------------------------------- #
# TC-CONF-010: v0.2.0 backward compatibility
# --------------------------------------------------------------------------- #
def test_v2_config_backward_compatible(tmp_path):
    """TC-CONF-010: v0.2.0-style config (no new fields) loads without error."""
    import yaml

    config = {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "openai",
                "type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
            }
        ],
        "routing": {"rules": [{"pattern": "gpt-4*", "provider": "openai"}]},
        "pipeline": {
            "detectors": {"input": [], "output": []},
        },
        "audit": {"enabled": False, "sanitize_logs": True},
    }
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.safe_dump(config))
    # Should load without error; new fields use defaults
    cfg = load_config(str(cfg_path))
    assert cfg.pipeline.streaming.mode == "sliding_window"
    assert cfg.pipeline.output_detection.mode == "sync"
    assert cfg.logging.level == "INFO"
