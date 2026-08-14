"""Unit tests for CORS configuration helpers.

Test cases: TC-CORS-001~003 (cors spec)
Covers: disabled CORS -> empty kwargs; enabled CORS -> allow_origins etc.;
origins mapping for preflight/actual requests.

The full create_app integration is owned by the fastapi-server slice (Slice 5);
the corresponding integration test is marked ``skip`` to avoid conflicting
with the middleware-chain registration performed there.
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.config.models import CORSConfig
from z_llm_safety_gateway.middleware.cors import (
    build_cors_middleware_kwargs,
    cors_enabled,
)


# --------------------------------------------------------------------------- #
# TC-CORS-001: CORS disabled by default -> empty kwargs (no middleware wiring)
# --------------------------------------------------------------------------- #
def test_cors_disabled_by_default() -> None:
    """TC-CORS-001: CORS default disabled -> no CORSMiddleware kwargs.

    GIVEN a default CORSConfig (enabled=False)
    WHEN build_cors_middleware_kwargs is called
    THEN an empty dict is returned (so no CORSMiddleware is wired)
    AND cors_enabled is False
    """
    config = CORSConfig()
    assert cors_enabled(config) is False
    assert build_cors_middleware_kwargs(config) == {}


def test_cors_explicit_disabled() -> None:
    """TC-CORS-001b: explicit enabled=False also yields empty kwargs."""
    config = CORSConfig(enabled=False, origins=["https://app.example.com"])
    assert build_cors_middleware_kwargs(config) == {}


# --------------------------------------------------------------------------- #
# TC-CORS-002: enabled CORS -> allow configured origins
# --------------------------------------------------------------------------- #
def test_cors_enabled_maps_origins() -> None:
    """TC-CORS-002: enabled CORS maps origins into CORSMiddleware kwargs.

    GIVEN CORSConfig enabled with origins=['https://app.example.com']
    WHEN build_cors_middleware_kwargs is called
    THEN allow_origins contains the configured origin
    AND allow_methods/allow_headers are provided for preflight handling
    """
    config = CORSConfig(enabled=True, origins=["https://app.example.com"])
    kwargs = build_cors_middleware_kwargs(config)

    assert kwargs["allow_origins"] == ["https://app.example.com"]
    assert "OPTIONS" in kwargs["allow_methods"]
    assert "POST" in kwargs["allow_methods"]
    assert kwargs["allow_headers"] == ["*"]
    assert kwargs["allow_credentials"] is False


def test_cors_enabled_preserves_multiple_origins() -> None:
    """TC-CORS-002b: multiple configured origins are all preserved."""
    origins = ["https://a.example.com", "https://b.example.com"]
    config = CORSConfig(enabled=True, origins=origins)
    kwargs = build_cors_middleware_kwargs(config)
    assert kwargs["allow_origins"] == origins


# --------------------------------------------------------------------------- #
# TC-CORS-003: integration into create_app (owned by Slice 5)
# --------------------------------------------------------------------------- #
@pytest.mark.skip(reason="create_app CORS wiring is owned by Slice 5 (fastapi-server integration)")
def test_cors_integration_into_create_app() -> None:
    """TC-CORS-003: create_app wiring is verified by the Slice 5 integration.

    This test is a placeholder that is skipped in this slice; the actual
    create_app + CORSMiddleware registration is implemented by the
    fastapi-server integration slice to avoid conflicting with the middleware
    chain registration.
    """
    assert True
