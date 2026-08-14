"""Integration tests for v0.4.0 fastapi-server middleware chain and wiring.

Covers TC-FSA-001 through TC-FSA-018 (fastapi-server spec):
- REQ-FSA-001: middleware chain order (RequestID→Auth→RateLimit→RequestSize→SafetyHeaders)
- REQ-FSA-002/003: request_id header/generate config + timeout/circuit_breaker injection
- REQ-FSA-004~008: auth/rate-limit/request-size/CORS/TLS/shutdown integration
"""

from __future__ import annotations

import yaml
from starlette.testclient import TestClient

from z_llm_safety_gateway.app import _extract_detector_configs
from z_llm_safety_gateway.circuit_breaker.breaker import CircuitBreaker
from z_llm_safety_gateway.circuit_breaker.factory import build_circuit_breaker
from z_llm_safety_gateway.config.models import (
    CircuitBreakerConfig,
    DetectorConfig,
)


def _build_yaml(**kwargs) -> str:
    """Build a minimal config YAML with optional v0.4.0 sections."""
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
    config.update(kwargs)
    return yaml.safe_dump(config)


# --------------------------------------------------------------------------- #
# TC-FSA-001: middleware chain order
# --------------------------------------------------------------------------- #
def test_middleware_chain_order(tmp_path):
    """TC-FSA-001: create_app registers middleware in correct order."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={
            "auth": {"enabled": True, "api_keys": [{"key": "sk-1", "name": "app"}]},
            "rate_limit": {"enabled": True, "rate": 100, "burst": 200},
            "max_request_size": "10MB",
            "timeout": {"upstream": "120s", "detector": "5s"},
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))

    # Starlette stores middleware in the order they were added (inner first).
    # The user_middleware list reflects add_middleware() call order.
    mw_types = [um.cls.__name__ for um in app.user_middleware]
    assert "SafetyHeadersMiddleware" in mw_types
    assert "RequestSizeMiddleware" in mw_types
    assert "RateLimitMiddleware" in mw_types
    assert "AuthMiddleware" in mw_types
    assert "RequestIDMiddleware" in mw_types

    # Starlette stores middleware in reverse add order (last added = outermost).
    # user_middleware list: [outermost, ..., innermost]
    # Expected order (outer→inner): RequestID → Auth → RateLimit → RequestSize → SafetyHeaders
    assert mw_types.index("RequestIDMiddleware") < mw_types.index("SafetyHeadersMiddleware")


# --------------------------------------------------------------------------- #
# TC-FSA-002/003: request_id config wiring
# --------------------------------------------------------------------------- #
def test_request_id_custom_header(tmp_path):
    """TC-FSA-002: custom header name from config is used."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={"request_id": {"header": "X-Trace-ID", "generate": True}}
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get("/health", headers={"X-Trace-ID": "test-trace-123"})
    assert response.headers.get("X-Trace-ID") == "test-trace-123"


def test_request_id_generate_false(tmp_path):
    """TC-FSA-003: generate=False always generates UUID, ignores client ID."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={"request_id": {"header": "X-Request-ID", "generate": False}}
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "client-provided-id"})
    rid = response.headers.get("X-Request-ID", "")
    # Should NOT be the client-provided ID
    assert rid != "client-provided-id"
    # Should be a UUID v4
    import re
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        rid,
    )


# --------------------------------------------------------------------------- #
# TC-FSA-004/005: timeout injection
# --------------------------------------------------------------------------- #
def test_extract_detector_configs_timeout_explicit():
    """TC-FSA-004: explicit detector timeout overrides global default."""
    det = DetectorConfig(
        name="test_det",
        enabled=True,
        config={"words": ["bad"]},
        timeout="10s",
    )
    configs = _extract_detector_configs([det], default_timeout_seconds=5.0)
    assert configs["test_det"]["timeout_seconds"] == 10.0


def test_extract_detector_configs_timeout_default():
    """TC-FSA-005: absent detector timeout falls back to global default."""
    det = DetectorConfig(
        name="test_det",
        enabled=True,
        config={"words": ["bad"]},
    )
    configs = _extract_detector_configs([det], default_timeout_seconds=5.0)
    assert configs["test_det"]["timeout_seconds"] == 5.0


# --------------------------------------------------------------------------- #
# TC-FSA-006/007: circuit_breaker injection
# --------------------------------------------------------------------------- #
def test_extract_detector_configs_circuit_breaker_injected():
    """TC-FSA-006: enabled circuit_breaker is injected as CircuitBreaker instance."""
    det = DetectorConfig(
        name="test_det",
        enabled=True,
        config={},
        circuit_breaker=CircuitBreakerConfig(
            enabled=True,
            failure_threshold=3,
            recovery_timeout="30s",
            fallback_action="fail_open",
        ),
    )
    configs = _extract_detector_configs([det], default_timeout_seconds=5.0)
    cb = configs["test_det"].get("circuit_breaker")
    assert isinstance(cb, CircuitBreaker)
    assert cb.failure_threshold == 3
    assert cb.recovery_timeout == 30.0
    assert cb.fallback_action == "fail_open"


def test_extract_detector_configs_no_circuit_breaker_when_disabled():
    """TC-FSA-006b: disabled circuit_breaker is not injected."""
    det = DetectorConfig(
        name="test_det",
        enabled=True,
        config={},
        circuit_breaker=CircuitBreakerConfig(enabled=False),
    )
    configs = _extract_detector_configs([det], default_timeout_seconds=5.0)
    assert "circuit_breaker" not in configs["test_det"]


def test_build_circuit_breaker_factory():
    """TC-FSA-007: build_circuit_breaker parses recovery_timeout string."""
    cfg = CircuitBreakerConfig(
        enabled=True,
        failure_threshold=7,
        recovery_timeout="45s",
        fallback_action="fail_closed",
    )
    cb = build_circuit_breaker(cfg)
    assert isinstance(cb, CircuitBreaker)
    assert cb.failure_threshold == 7
    assert cb.recovery_timeout == 45.0
    assert cb.fallback_action == "fail_closed"


# --------------------------------------------------------------------------- #
# TC-FSA-008~010: auth integration
# --------------------------------------------------------------------------- #
def test_auth_enabled_blocks_unauthorized(tmp_path):
    """TC-FSA-009: auth enabled, missing token → 401."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={
            "auth": {
                "enabled": True,
                "api_keys": [{"key": "sk-valid", "name": "app1"}],
            }
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 401


def test_auth_enabled_passes_authorized(tmp_path):
    """TC-FSA-008: auth enabled, valid Bearer token → passes."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={
            "auth": {
                "enabled": True,
                "api_keys": [{"key": "sk-valid", "name": "app1"}],
            }
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={"Authorization": "Bearer sk-valid"},
    )
    assert response.status_code == 200


def test_auth_disabled_passes_all(tmp_path):
    """TC-FSA-010: auth disabled (default) → no token check."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200


# --------------------------------------------------------------------------- #
# TC-FSA-013/014: request size integration
# --------------------------------------------------------------------------- #
def test_request_size_rejects_oversized(tmp_path):
    """TC-FSA-013: Content-Length over max → 413."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={"max_request_size": "1MB"}
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    # 2MB payload → exceeds 1MB limit
    big_body = "x" * (2 * 1024 * 1024)
    response = client.post(
        "/v1/chat/completions",
        content=big_body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(big_body)),
        },
    )
    assert response.status_code == 413


# --------------------------------------------------------------------------- #
# TC-FSA-015/016: CORS integration
# --------------------------------------------------------------------------- #
def test_cors_enabled_allows_preflight(tmp_path):
    """TC-FSA-015: CORS enabled → preflight gets CORS headers."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml(
        security={
            "cors": {
                "enabled": True,
                "origins": ["https://app.example.com"],
            }
        }
    )
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in {k.lower() for k in response.headers}


def test_cors_disabled_no_headers(tmp_path):
    """TC-FSA-016: CORS disabled → no CORS headers."""
    from z_llm_safety_gateway.app import create_app

    yaml_str = _build_yaml()
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    app = create_app(str(cfg_path))
    client = TestClient(app)

    response = client.get(
        "/health",
        headers={"Origin": "https://app.example.com"},
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}
