"""Unit tests for v0.4.0 SecurityConfig refactor.

Covers TC-CFG-001 through TC-CFG-005 (config-system spec):
- REQ-CFG-001: SecurityConfig typed sub-models (Auth/TLS/RateLimit/CORS/RequestID/Timeout)
- REQ-CFG-002: ServerConfig workers/stop_timeout
- REQ-CFG-003: ObservabilityConfig nested sub-models
- REQ-CFG-004: threshold namespace separation (count vs confidence)
- REQ-CFG-005: PII naming unified to pii_redaction
"""

from __future__ import annotations

import pytest
import yaml

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.models import GatewayConfig
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _build_yaml(security: dict | None = None, server: dict | None = None,
                observability: dict | None = None, pipeline: dict | None = None) -> str:
    """Build a minimal valid config YAML with optional v0.4.0 sections."""
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
        "pipeline": {"detectors": {"input": [], "output": []}},
    }
    if security is not None:
        config["security"] = security
    if server is not None:
        config["server"] = server
    if observability is not None:
        config["observability"] = observability
    if pipeline is not None:
        config["pipeline"] = pipeline
    return yaml.safe_dump(config)


def _load(tmp_path, yaml_str: str) -> GatewayConfig:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    return load_config(str(cfg_path))


# --------------------------------------------------------------------------- #
# TC-CFG-001: SecurityConfig typed sub-models
# --------------------------------------------------------------------------- #
def test_security_full_parse(tmp_path):
    """TC-CFG-001: full security section parses into typed sub-models."""
    yaml_str = _build_yaml(
        security={
            "auth": {
                "enabled": True,
                "api_keys": [{"key": "sk-1", "name": "app-1"}],
            },
            "tls": {"enabled": True, "cert_file": "/c.pem", "key_file": "/k.pem"},
            "rate_limit": {
                "enabled": True,
                "strategy": "token_bucket",
                "rate": 100,
                "burst": 200,
                "per": "api_key",
                "storage": "memory",
            },
            "cors": {"enabled": True, "origins": ["https://app.example.com"]},
            "request_id": {"header": "X-Trace-ID", "generate": False},
            "max_request_size": "5MB",
            "timeout": {"upstream": "120s", "detector": "5s"},
        }
    )
    cfg = _load(tmp_path, yaml_str)
    sec = cfg.security
    assert sec.auth.enabled is True
    assert sec.auth.api_keys[0].key == "sk-1"
    assert sec.auth.api_keys[0].name == "app-1"
    assert sec.tls.enabled is True
    assert sec.tls.cert_file == "/c.pem"
    assert sec.tls.key_file == "/k.pem"
    assert sec.rate_limit.enabled is True
    assert sec.rate_limit.strategy == "token_bucket"
    assert sec.rate_limit.rate == 100
    assert sec.rate_limit.burst == 200
    assert sec.rate_limit.per == "api_key"
    assert sec.rate_limit.storage == "memory"
    assert sec.cors.enabled is True
    assert sec.cors.origins == ["https://app.example.com"]
    assert sec.request_id.header == "X-Trace-ID"
    assert sec.request_id.generate is False
    assert sec.max_request_size == "5MB"


def test_security_defaults(tmp_path):
    """TC-CFG-001b: absent security section uses defaults."""
    yaml_str = _build_yaml()
    cfg = _load(tmp_path, yaml_str)
    sec = cfg.security
    assert sec.auth.enabled is False
    assert sec.auth.api_keys == []
    assert sec.tls.enabled is False
    assert sec.rate_limit.enabled is False
    assert sec.cors.enabled is False
    assert sec.request_id.header == "X-Request-ID"
    assert sec.request_id.generate is True
    assert sec.max_request_size == "10MB"
    assert sec.timeout.upstream == "120s"
    assert sec.timeout.detector == "5s"
    assert sec.timeout.upstream_seconds == 120.0
    assert sec.timeout.detector_seconds == 5.0


# --------------------------------------------------------------------------- #
# TC-CFG-001c: TimeConfig duration parsing
# --------------------------------------------------------------------------- #
def test_timeout_duration_parsing(tmp_path):
    """TC-CFG-001c: '120s'/'5s' strings parsed to seconds."""
    yaml_str = _build_yaml(
        security={"timeout": {"upstream": "120s", "detector": "5s"}}
    )
    cfg = _load(tmp_path, yaml_str)
    assert cfg.security.timeout.upstream_seconds == 120.0
    assert cfg.security.timeout.detector_seconds == 5.0


# --------------------------------------------------------------------------- #
# TC-CFG-002: ServerConfig workers/stop_timeout
# --------------------------------------------------------------------------- #
def test_server_workers_stop_timeout(tmp_path):
    """TC-CFG-002: server.workers and server.stop_timeout parse."""
    yaml_str = _build_yaml(
        server={"host": "0.0.0.0", "port": 8080, "workers": 4, "stop_timeout": "30s"}
    )
    cfg = _load(tmp_path, yaml_str)
    assert cfg.server.workers == 4
    assert cfg.server.stop_timeout == "30s"


def test_server_defaults(tmp_path):
    """TC-CFG-002b: server defaults workers=1, stop_timeout='30s'."""
    yaml_str = _build_yaml()
    cfg = _load(tmp_path, yaml_str)
    assert cfg.server.workers == 1
    assert cfg.server.stop_timeout == "30s"


# --------------------------------------------------------------------------- #
# TC-CFG-003: ObservabilityConfig nested sub-models
# --------------------------------------------------------------------------- #
def test_observability_nested_parse(tmp_path):
    """TC-CFG-003: observability metrics/tracing nested parse."""
    yaml_str = _build_yaml(
        observability={
            "metrics": {"enabled": True, "endpoint": "/metrics"},
            "tracing": {
                "enabled": True,
                "exporter": "otlp",
                "endpoint": "http://collector:4317",
                "sample_rate": 0.1,
            },
        }
    )
    cfg = _load(tmp_path, yaml_str)
    obs = cfg.observability
    assert obs.metrics.enabled is True
    assert obs.metrics.endpoint == "/metrics"
    assert obs.tracing.enabled is True
    assert obs.tracing.exporter == "otlp"
    assert obs.tracing.endpoint == "http://collector:4317"
    assert obs.tracing.sample_rate == 0.1


def test_observability_defaults(tmp_path):
    """TC-CFG-003b: observability defaults metrics disabled, sample_rate 0.1."""
    yaml_str = _build_yaml()
    cfg = _load(tmp_path, yaml_str)
    assert cfg.observability.metrics.enabled is False
    assert cfg.observability.metrics.endpoint == "/metrics"
    assert cfg.observability.tracing.enabled is False
    assert cfg.observability.tracing.sample_rate == 0.1


# --------------------------------------------------------------------------- #
# TC-CFG-004: threshold namespace separation
# --------------------------------------------------------------------------- #
def test_count_threshold_separate_validation(tmp_path):
    """TC-CFG-004: count thresholds validated independently of confidence."""
    yaml_str = _build_yaml(
        pipeline={
            "detectors": {
                "input": [
                    {
                        "name": "sensitive_words",
                        "enabled": True,
                        "config": {
                            "count_block_threshold": 3,
                            "count_flag_threshold": 1,
                            "words": ["bad"],
                        },
                    }
                ],
                "output": [],
            }
        }
    )
    cfg = _load(tmp_path, yaml_str)
    det_cfg = cfg.pipeline.detectors.input[0].config
    assert det_cfg["count_block_threshold"] == 3
    assert det_cfg["count_flag_threshold"] == 1


def test_count_threshold_invalid_order(tmp_path):
    """TC-CFG-004b: count_block <= count_flag raises validation error."""
    yaml_str = _build_yaml(
        pipeline={
            "detectors": {
                "input": [
                    {
                        "name": "sensitive_words",
                        "enabled": True,
                        "config": {
                            "count_block_threshold": 1,
                            "count_flag_threshold": 3,
                            "words": ["bad"],
                        },
                    }
                ],
                "output": [],
            }
        }
    )
    with pytest.raises(ConfigValidationError):
        _load(tmp_path, yaml_str)


# --------------------------------------------------------------------------- #
# TC-CFG-005: PII naming unified
# --------------------------------------------------------------------------- #
def test_pii_detector_name_is_pii_redaction(tmp_path):
    """TC-CFG-005: PIIDetector.name equals 'pii_redaction'."""
    from z_llm_safety_gateway.detectors.pii import PIIDetector

    assert PIIDetector.name == "pii_redaction"


def test_pii_config_retrieved_by_registry_name(tmp_path):
    """TC-CFG-005b: engine config lookup uses registered name pii_redaction."""
    from z_llm_safety_gateway.detectors import create_default_registry

    registry = create_default_registry()
    assert "pii_redaction" in registry._detectors
    assert registry._detectors["pii_redaction"].name == "pii_redaction"
