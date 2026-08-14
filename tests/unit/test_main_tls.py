"""Unit tests for TLS integration and graceful shutdown in __main__.

Test cases:
- TC-TLS-001~003 (tls spec): TLS disabled -> no ssl kwargs; TLS enabled ->
  ssl_certfile/ssl_keyfile passed; TLS enabled with missing files -> rejected.
- TC-GS-001~003 (graceful-shutdown spec): lifespan shutdown flushes audit
  logs; stop_timeout -> uvicorn timeout_graceful_shutdown; graceful_shutdown
  utility flushes audit logs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import z_llm_safety_gateway.__main__ as main_mod
from z_llm_safety_gateway.app import lifespan
from z_llm_safety_gateway.config.loader import load_config


def _build_yaml(tls: dict | None = None, stop_timeout: str | None = None) -> str:
    """Build a minimal valid config YAML with optional v0.4.0 security sections."""
    config: dict[str, Any] = {
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
    if stop_timeout is not None:
        config["server"]["stop_timeout"] = stop_timeout
    if tls is not None:
        config["security"] = {"tls": tls}
    return __import__("yaml").safe_dump(config)


def _load(tmp_path: Path, yaml_str: str):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml_str)
    return load_config(str(cfg_path))


def _make_cert(tmp_path: Path, name: str) -> Path:
    """Create a placeholder cert/key file on disk."""
    path = tmp_path / name
    path.write_text("placeholder")
    return path


# --------------------------------------------------------------------------- #
# TC-TLS-001: TLS disabled -> uvicorn started without ssl kwargs (HTTP)
# --------------------------------------------------------------------------- #
def test_tls_disabled_omits_ssl_kwargs(tmp_path) -> None:
    """TC-TLS-001: TLS disabled -> no ssl_certfile/ssl_keyfile in uvicorn kwargs.

    GIVEN config without security.tls (or enabled: false)
    WHEN build_server_kwargs computes uvicorn.run kwargs
    THEN ssl_certfile and ssl_keyfile are absent
    AND no TLS startup error is produced
    """
    cfg = _load(tmp_path, _build_yaml())
    kwargs = main_mod.build_server_kwargs(cfg, "127.0.0.1", 8080)

    assert "ssl_certfile" not in kwargs
    assert "ssl_keyfile" not in kwargs
    # Graceful shutdown timeout is still present.
    assert kwargs["timeout_graceful_shutdown"] == 30


def test_tls_explicit_disabled_omits_ssl_kwargs(tmp_path) -> None:
    """TC-TLS-001b: explicit enabled: false also omits ssl kwargs."""
    cfg = _load(tmp_path, _build_yaml(tls={"enabled": False}))
    kwargs = main_mod.build_server_kwargs(cfg, "127.0.0.1", 8080)

    assert "ssl_certfile" not in kwargs
    assert "ssl_keyfile" not in kwargs


# --------------------------------------------------------------------------- #
# TC-TLS-002: TLS enabled -> ssl_certfile/ssl_keyfile passed to uvicorn
# --------------------------------------------------------------------------- #
def test_tls_enabled_passes_cert_and_key(tmp_path) -> None:
    """TC-TLS-002: TLS enabled -> uvicorn receives ssl_certfile/ssl_keyfile.

    GIVEN security.tls.enabled=true with valid cert/key file paths
    WHEN build_server_kwargs computes uvicorn.run kwargs
    THEN ssl_certfile=<cert_file> and ssl_keyfile=<key_file> are present
    """
    cert = _make_cert(tmp_path, "cert.pem")
    key = _make_cert(tmp_path, "key.pem")
    cfg = _load(
        tmp_path,
        _build_yaml(
            tls={
                "enabled": True,
                "cert_file": str(cert),
                "key_file": str(key),
            }
        ),
    )
    kwargs = main_mod.build_server_kwargs(cfg, "127.0.0.1", 8080)

    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)


# --------------------------------------------------------------------------- #
# TC-TLS-003: TLS enabled but cert/key missing -> reject startup
# --------------------------------------------------------------------------- #
def test_tls_missing_cert_rejected(tmp_path) -> None:
    """TC-TLS-003: TLS enabled with a missing cert file rejects startup.

    GIVEN security.tls.enabled=true and cert_file points to a missing file
    WHEN validate_tls_config is called
    THEN a clear error is raised naming the missing file path
    AND the gateway does not silently degrade to plaintext HTTP
    """
    key = _make_cert(tmp_path, "key.pem")
    missing_cert = tmp_path / "does-not-exist.pem"
    cfg = _load(
        tmp_path,
        _build_yaml(
            tls={
                "enabled": True,
                "cert_file": str(missing_cert),
                "key_file": str(key),
            }
        ),
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        main_mod.validate_tls_config(cfg)

    assert str(missing_cert) in str(excinfo.value)


def test_tls_missing_key_rejected(tmp_path) -> None:
    """TC-TLS-003b: TLS enabled with a missing key file rejects startup."""
    cert = _make_cert(tmp_path, "cert.pem")
    missing_key = tmp_path / "does-not-exist-key.pem"
    cfg = _load(
        tmp_path,
        _build_yaml(
            tls={
                "enabled": True,
                "cert_file": str(cert),
                "key_file": str(missing_key),
            }
        ),
    )

    with pytest.raises(FileNotFoundError) as excinfo:
        main_mod.validate_tls_config(cfg)

    assert str(missing_key) in str(excinfo.value)


# --------------------------------------------------------------------------- #
# TC-GS-001: Lifespan shutdown flushes audit logs (replaces signal handlers)
# --------------------------------------------------------------------------- #
async def test_lifespan_shutdown_flushes_audit_logger() -> None:
    """TC-GS-001: lifespan shutdown flushes and closes the audit logger.

    GIVEN a FastAPI app with the lifespan handler and an audit logger
    WHEN the lifespan context exits (simulating uvicorn SIGTERM shutdown)
    THEN the audit logger is flushed and closed
    """
    audit_logger = SimpleNamespace(flushed=0, closed=0)
    audit_logger.flush = lambda: setattr(audit_logger, "flushed", audit_logger.flushed + 1)
    audit_logger.close = lambda: setattr(audit_logger, "closed", audit_logger.closed + 1)
    app = SimpleNamespace(state=SimpleNamespace(audit_logger=audit_logger))

    async with lifespan(app):
        pass  # startup — nothing to do

    assert audit_logger.flushed == 1
    assert audit_logger.closed == 1


async def test_lifespan_shutdown_without_audit_logger_is_noop() -> None:
    """TC-GS-001b: lifespan shutdown is safe when no audit logger is configured."""
    app = SimpleNamespace(state=SimpleNamespace(audit_logger=None))
    # Should not raise.
    async with lifespan(app):
        pass


# --------------------------------------------------------------------------- #
# TC-GS-002: server.stop_timeout -> uvicorn timeout_graceful_shutdown
# --------------------------------------------------------------------------- #
def test_stop_timeout_default_passed_to_uvicorn(tmp_path) -> None:
    """TC-GS-002: default stop_timeout '30s' -> timeout_graceful_shutdown=30."""
    cfg = _load(tmp_path, _build_yaml())
    kwargs = main_mod.build_server_kwargs(cfg, "127.0.0.1", 8080)
    assert kwargs["timeout_graceful_shutdown"] == 30


def test_stop_timeout_custom_passed_to_uvicorn(tmp_path) -> None:
    """TC-GS-002b: custom stop_timeout is passed to uvicorn."""
    cfg = _load(tmp_path, _build_yaml(stop_timeout="60s"))
    kwargs = main_mod.build_server_kwargs(cfg, "127.0.0.1", 8080)
    assert kwargs["timeout_graceful_shutdown"] == 60


# --------------------------------------------------------------------------- #
# TC-GS-003: graceful shutdown flushes audit logs and releases resources
# --------------------------------------------------------------------------- #
def test_graceful_shutdown_flushes_audit_logger() -> None:
    """TC-GS-003: shutdown flushes and closes the audit logger."""
    audit_logger = SimpleNamespace(flushed=0, closed=0)
    audit_logger.flush = lambda: setattr(audit_logger, "flushed", audit_logger.flushed + 1)
    audit_logger.close = lambda: setattr(audit_logger, "closed", audit_logger.closed + 1)
    app = SimpleNamespace(state=SimpleNamespace(audit_logger=audit_logger))

    main_mod.graceful_shutdown(app)

    assert audit_logger.flushed == 1
    assert audit_logger.closed == 1


def test_graceful_shutdown_without_audit_logger_is_noop() -> None:
    """TC-GS-003b: shutdown is safe when no audit logger is configured."""
    app = SimpleNamespace(state=SimpleNamespace(audit_logger=None))
    # Should not raise.
    main_mod.graceful_shutdown(app)
