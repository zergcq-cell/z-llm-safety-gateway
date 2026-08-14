"""CORS configuration helpers (v0.4.0).

Provides pure, independently-testable helpers that translate ``security.cors``
config into Starlette ``CORSMiddleware`` keyword arguments.

Integration note (TODO - fastapi-server / Slice 5): wiring ``CORSMiddleware``
into the FastAPI :func:`create_app` factory is owned by the fastapi-server
integration slice (Slice 5), which registers the full middleware chain. This
module intentionally does NOT modify ``app.py``; it only implements the
config -> kwargs mapping so the CORS behavior can be unit-tested in isolation.
"""

from __future__ import annotations

from typing import Any

from z_llm_safety_gateway.config.models import CORSConfig

#: HTTP methods allowed on cross-origin (preflight and actual) requests.
DEFAULT_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
#: Request headers allowed on cross-origin requests (wildcard).
DEFAULT_ALLOW_HEADERS = ["*"]
#: Whether cross-origin requests may include credentials (default off).
DEFAULT_ALLOW_CREDENTIALS = False


def cors_enabled(cors_config: CORSConfig) -> bool:
    """Return whether CORS should be enabled for the given config.

    Args:
        cors_config: The parsed ``security.cors`` configuration.

    Returns:
        ``True`` when CORS is enabled, ``False`` otherwise.
    """
    return cors_config.enabled


def build_cors_middleware_kwargs(cors_config: CORSConfig) -> dict[str, Any]:
    """Build keyword arguments for :class:`starlette.CORSMiddleware`.

    Returns an empty dict when CORS is disabled so callers can skip wiring
    the middleware entirely (REQ-CORS-001).

    Args:
        cors_config: The parsed ``security.cors`` configuration.

    Returns:
        A dict of kwargs accepted by ``CORSMiddleware`` (``allow_origins``,
        ``allow_methods``, ``allow_headers``, ``allow_credentials``), or an
        empty dict when CORS is disabled.
    """
    if not cors_config.enabled:
        return {}
    return {
        "allow_origins": list(cors_config.origins),
        "allow_methods": list(DEFAULT_ALLOW_METHODS),
        "allow_headers": list(DEFAULT_ALLOW_HEADERS),
        "allow_credentials": DEFAULT_ALLOW_CREDENTIALS,
    }
