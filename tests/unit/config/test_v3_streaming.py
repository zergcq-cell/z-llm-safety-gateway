"""Unit tests for v0.3.0 streaming / output_detection config models.

Covers TC-CONF-001 through TC-CONF-006 (sse-streaming/config-system spec).
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _build_yaml(**pipeline_overrides: object) -> str:
    """Build a minimal valid config YAML with pipeline section overrides."""
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
        "pipeline": pipeline_overrides,
    }
    return yaml.safe_dump(config)


# --------------------------------------------------------------------------- #
# TC-CONF-001: streaming config block parsing + defaults
# --------------------------------------------------------------------------- #
def test_streaming_config_full_parse(tmp_path):
    """TC-CONF-001: full streaming block parses into StreamingConfig."""
    yaml_str = _build_yaml(
        streaming={
            "mode": "sliding_window",
            "window_size": 200,
            "overlap": 50,
            "send_flag_events": False,
            "max_response_size": "1MB",
            "on_max_size": "block",
            "post_audit": True,
            "recall": {"method": "sse", "webhook_url": "", "webhook_auth_header": ""},
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    streaming = cfg.pipeline.streaming
    assert streaming.mode == "sliding_window"
    assert streaming.window_size == 200
    assert streaming.overlap == 50
    assert streaming.send_flag_events is False
    assert streaming.max_response_size == "1MB"
    assert streaming.on_max_size == "block"
    assert streaming.post_audit is True
    assert streaming.recall.method == "sse"


def test_streaming_config_defaults(tmp_path):
    """TC-CONF-001b: absent streaming block uses all defaults."""
    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    streaming = cfg.pipeline.streaming
    assert streaming.mode == "sliding_window"
    assert streaming.window_size == 200
    assert streaming.overlap == 50
    assert streaming.send_flag_events is False
    assert streaming.on_max_size == "block"
    assert streaming.post_audit is True
    assert streaming.recall.method == "sse"


# --------------------------------------------------------------------------- #
# TC-CONF-002: invalid streaming.mode
# --------------------------------------------------------------------------- #
def test_streaming_mode_invalid(tmp_path):
    """TC-CONF-002: invalid streaming.mode raises validation error."""
    yaml_str = _build_yaml(streaming={"mode": "tokenizer"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    with pytest.raises(ConfigValidationError):
        load_config(str(cfg_path))


# --------------------------------------------------------------------------- #
# TC-CONF-003: invalid on_max_size
# --------------------------------------------------------------------------- #
def test_streaming_on_max_size_invalid(tmp_path):
    """TC-CONF-003: invalid on_max_size raises validation error."""
    yaml_str = _build_yaml(streaming={"on_max_size": "stop"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    with pytest.raises(ConfigValidationError):
        load_config(str(cfg_path))


# --------------------------------------------------------------------------- #
# TC-CONF-004: output_detection config parsing
# --------------------------------------------------------------------------- #
def test_output_detection_async_parse(tmp_path):
    """TC-CONF-004: async output_detection with webhook parses."""
    yaml_str = _build_yaml(
        output_detection={
            "mode": "async",
            "sync_timeout": "5s",
            "recall": {
                "webhook_url": "http://hooks.example.com/recall",
                "webhook_auth_header": "Bearer x",
            },
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    od = cfg.pipeline.output_detection
    assert od.mode == "async"
    assert od.sync_timeout == "5s"
    assert od.recall.webhook_url == "http://hooks.example.com/recall"
    assert od.recall.webhook_auth_header == "Bearer x"


def test_output_detection_sync_default(tmp_path):
    """TC-CONF-004b: absent output_detection defaults to sync mode."""
    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    cfg = load_config(str(cfg_path))
    assert cfg.pipeline.output_detection.mode == "sync"


# --------------------------------------------------------------------------- #
# TC-CONF-005: async mode requires webhook_url
# --------------------------------------------------------------------------- #
def test_output_detection_async_requires_webhook(tmp_path):
    """TC-CONF-005: async mode with empty webhook_url raises validation error."""
    yaml_str = _build_yaml(output_detection={"mode": "async"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    with pytest.raises(ConfigValidationError):
        load_config(str(cfg_path))


# --------------------------------------------------------------------------- #
# TC-CONF-006: invalid output_detection.mode
# --------------------------------------------------------------------------- #
def test_output_detection_mode_invalid(tmp_path):
    """TC-CONF-006: invalid output_detection.mode raises validation error."""
    yaml_str = _build_yaml(output_detection={"mode": "offline"})
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    with pytest.raises(ConfigValidationError):
        load_config(str(cfg_path))
