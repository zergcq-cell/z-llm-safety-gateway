"""CLI entry point for the z LLM Safety Gateway.

Responsible for:
- Parsing CLI arguments and loading configuration.
- Native TLS termination (v0.4.0): when ``security.tls.enabled``, uvicorn is
  started with ``ssl_certfile``/``ssl_keyfile``; missing cert/key files reject
  startup with a clear error rather than silently degrading to plaintext HTTP.
- Graceful shutdown (v0.4.0): ``server.stop_timeout`` is forwarded to uvicorn
  as ``timeout_graceful_shutdown``.  Audit log flushing is handled by the
  FastAPI lifespan context manager in ``app.py``, which uvicorn triggers
  on SIGTERM/SIGINT — avoiding conflicts with uvicorn's own signal handlers.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import structlog
import uvicorn

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.models import GatewayConfig, _parse_duration

logger = structlog.get_logger(__name__)


def validate_tls_config(config: GatewayConfig) -> None:
    """Reject startup when TLS is enabled but a cert/key file is missing.

    Args:
        config: The loaded gateway configuration.

    Raises:
        FileNotFoundError: If TLS is enabled and ``cert_file`` or ``key_file``
            does not reference an existing file.
    """
    tls = config.security.tls
    if not tls.enabled:
        return

    missing: list[str] = []
    for field, path in (("cert_file", tls.cert_file), ("key_file", tls.key_file)):
        if not path or not Path(path).is_file():
            missing.append(f"{field}='{path}'")

    if missing:
        raise FileNotFoundError(
            "TLS enabled but certificate/key file(s) missing or unreadable: "
            + ", ".join(missing)
        )


def build_server_kwargs(config: GatewayConfig, host: str, port: int) -> dict[str, Any]:
    """Build the keyword arguments passed to :func:`uvicorn.run`.

    Includes native TLS termination (when enabled) and the graceful shutdown
    timeout derived from ``server.stop_timeout``.

    Args:
        config: The loaded gateway configuration.
        host: The host to bind.
        port: The port to bind.

    Returns:
        A dict of keyword arguments for :func:`uvicorn.run`.
    """
    kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "timeout_graceful_shutdown": int(_parse_duration(config.server.stop_timeout)),
    }

    tls = config.security.tls
    if tls.enabled:
        kwargs["ssl_certfile"] = tls.cert_file
        kwargs["ssl_keyfile"] = tls.key_file

    return kwargs


def graceful_shutdown(app: Any) -> None:
    """Flush audit logs and release resources during shutdown.

    Args:
        app: The FastAPI application exposing ``app.state.audit_logger``.
    """
    audit_logger = getattr(getattr(app, "state", None), "audit_logger", None)
    if audit_logger is not None:
        try:
            audit_logger.flush()
            audit_logger.close()
        except Exception:  # pragma: no cover - defensive, shutdown must not hang
            logger.warning("audit_shutdown_flush_failed", exc_info=True)
    logger.info("graceful_shutdown_complete")


def main() -> None:
    """Parse CLI arguments and start the gateway server."""
    parser = argparse.ArgumentParser(
        description="z LLM Safety Gateway — LLM content safety gateway"
    )
    parser.add_argument(
        "--config",
        default="config/gateway.yaml",
        help="Path to the YAML configuration file (default: config/gateway.yaml)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Override server host from config",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override server port from config",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    host = args.host or config.server.host
    port = args.port or config.server.port

    # Reject startup before binding if TLS is enabled but misconfigured.
    validate_tls_config(config)

    app = create_app(args.config)

    uvicorn.run(app, **build_server_kwargs(config, host, port))


if __name__ == "__main__":
    main()
