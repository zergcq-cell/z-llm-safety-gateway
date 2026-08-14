"""Unit tests for v0.5.0 gRPC detector config extensions (TC-CFG-501/502/503).

Test cases:
- TC-CFG-501: type=grpc parsed; gateway-internal fields (endpoint/tls_enabled/
  tls_ca_file) separated from passthrough fields via passthrough_config()
- TC-CFG-502: type=grpc without endpoint -> startup error
- TC-CFG-503: type=grpc without circuit_breaker -> Info warning
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.models import GatewayConfig, passthrough_config
from z_llm_safety_gateway.config.validators import ConfigValidationError, validate_config


def _build_yaml(grpc_config: dict, *, name: str = "acme_guard") -> str:
    """Build a minimal config YAML with one gRPC detector."""
    import yaml

    cfg = {
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
            "detectors": {
                "input": [
                    {
                        "name": name,
                        "type": "grpc",
                        "enabled": True,
                        "config": grpc_config,
                    }
                ],
                "output": [],
            }
        },
    }
    return yaml.safe_dump(cfg)


def _load(tmp_path, yaml_str: str) -> GatewayConfig:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    return _load_via_loader(str(cfg_path))


def _load_via_loader(path: str) -> GatewayConfig:
    from z_llm_safety_gateway.config.loader import load_config

    return load_config(path)


# --------------------------------------------------------------------------- #
# TC-CFG-501: type=grpc parsing + passthrough field separation
# --------------------------------------------------------------------------- #
def test_type_grpc_accepted_with_full_config(tmp_path) -> None:
    """TC-CFG-501: type=grpc accepted; all config fields preserved."""
    cfg = _load(
        tmp_path,
        _build_yaml(
            {
                "endpoint": "localhost:50051",
                "api_key": "sk-secret",
                "sensitivity": "high",
            }
        ),
    )
    detector = cfg.pipeline.detectors.input[0]
    assert detector.type == "grpc"
    assert detector.config["endpoint"] == "localhost:50051"
    assert detector.config["api_key"] == "sk-secret"
    # Validation passes (endpoint present).
    validate_config(cfg)


def test_passthrough_config_excludes_gateway_fields() -> None:
    """TC-CFG-501b: passthrough_config strips endpoint/tls_enabled/tls_ca_file."""
    raw = {
        "endpoint": "localhost:50051",
        "tls_enabled": True,
        "tls_ca_file": "/certs/ca.pem",
        "api_key": "sk-secret",
        "license_key": "lic-1",
        "sensitivity": "high",
    }
    passthrough = passthrough_config(raw)
    assert "endpoint" not in passthrough
    assert "tls_enabled" not in passthrough
    assert "tls_ca_file" not in passthrough
    assert passthrough == {"api_key": "sk-secret", "license_key": "lic-1", "sensitivity": "high"}


def test_passthrough_config_empty_config() -> None:
    """TC-CFG-501c: empty config -> empty passthrough."""
    assert passthrough_config({}) == {}


# --------------------------------------------------------------------------- #
# TC-CFG-502: type=grpc missing endpoint -> error
# --------------------------------------------------------------------------- #
def test_type_grpc_missing_endpoint_rejected(tmp_path) -> None:
    """TC-CFG-502: type=grpc without endpoint raises ConfigValidationError."""
    with pytest.raises(ConfigValidationError) as excinfo:
        _load(tmp_path, _build_yaml({"api_key": "sk-secret"}))
    assert "gRPC detector 'acme_guard' is missing required config: endpoint" in str(
        excinfo.value
    )


def test_type_grpc_empty_endpoint_rejected(tmp_path) -> None:
    """TC-CFG-502b: type=grpc with empty endpoint also rejected."""
    with pytest.raises(ConfigValidationError):
        _load(tmp_path, _build_yaml({"endpoint": ""}))


# --------------------------------------------------------------------------- #
# TC-CFG-503: type=grpc without circuit_breaker -> Info warning
# --------------------------------------------------------------------------- #
def test_type_grpc_no_circuit_breaker_warns(tmp_path) -> None:
    """TC-CFG-503: type=grpc without circuit_breaker emits a UserWarning."""
    cfg = _load(tmp_path, _build_yaml({"endpoint": "localhost:50051"}))
    with pytest.warns(UserWarning, match="no circuit_breaker configured"):
        validate_config(cfg)


def test_type_grpc_with_circuit_breaker_no_warning(tmp_path) -> None:
    """TC-CFG-503b: type=grpc with circuit_breaker does not warn."""
    import warnings

    import yaml

    yaml_str = _build_yaml({"endpoint": "localhost:50051"})
    raw = yaml.safe_load(yaml_str)
    raw["pipeline"]["detectors"]["input"][0]["circuit_breaker"] = {
        "enabled": True,
        "failure_threshold": 5,
        "recovery_timeout": "30s",
        "fallback_action": "fail_open",
    }
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        _load(tmp_path, yaml.safe_dump(raw))
    assert not any("no circuit_breaker" in str(w.message) for w in record)
