"""Unit tests for the FastAPI application factory — TC-FASTAPI-001, 002, 008.

Covers: create_app() factory function, config loading, route/middleware/handler
registration, and import-side-effect safety.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from z_llm_safety_gateway.exceptions import ConfigError
from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware
from z_llm_safety_gateway.providers.base import ProviderError


def _collect_route_paths(app: FastAPI) -> set[str]:
    """Collect all registered route paths, traversing _IncludedRouter wrappers.

    In FastAPI 0.141+, included routers are stored as _IncludedRouter objects
    that wrap the original APIRouter.  This helper traverses both top-level
    routes and routes nested inside _IncludedRouter.original_router.
    """
    paths: set[str] = set()
    for route in app.routes:
        # Direct route with a path attribute
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(path)
        # _IncludedRouter wraps an original APIRouter
        original_router: Any = getattr(route, "original_router", None)
        if original_router is not None:
            for sub_route in original_router.routes:
                sub_path = getattr(sub_route, "path", None)
                if sub_path is not None:
                    paths.add(sub_path)
    return paths

TEST_CONFIG_YAML = """
server:
  host: "127.0.0.1"
  port: 8080

providers:
  - name: "openai"
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "test-key"

routing:
  rules:
    - pattern: "gpt-4*"
      provider: "openai"

security:
  timeout:
    upstream: 5
"""


@pytest.fixture
def config_path(tmp_path: Path) -> str:
    """Write a test config file and return its path."""
    path = tmp_path / "test_config.yaml"
    path.write_text(TEST_CONFIG_YAML)
    return str(path)


@pytest.fixture(autouse=True)
def reset_ready_state() -> None:
    """Reset the global _ready flag to False after each test."""
    yield
    from z_llm_safety_gateway.routes.health import set_ready

    set_ready(False)


# ---------------------------------------------------------------------------
# TC-FASTAPI-001: create_app returns FastAPI with config, routes, middleware,
#                 and exception handlers all registered.
# ---------------------------------------------------------------------------


def test_create_app_returns_fastapi_instance(config_path: str) -> None:
    """TC-FASTAPI-001: create_app returns a FastAPI instance with all components registered.

    GIVEN a valid config file path
    WHEN create_app(config_path) is called
    THEN a FastAPI instance is returned
    AND the config is loaded into app.state
    AND routes /v1/chat/completions, /v1/models, /health, /ready, /metrics are registered
    AND RequestIDMiddleware is registered
    AND exception handlers for ProviderError, ConfigError, and Exception are registered
    """
    from z_llm_safety_gateway.app import create_app

    app = create_app(config_path)

    assert isinstance(app, FastAPI)

    # Config is loaded
    assert hasattr(app.state, "config")
    assert app.state.config.server.host == "127.0.0.1"
    assert app.state.config.server.port == 8080

    # Router is stored in app.state
    assert hasattr(app.state, "router")

    # Routes are registered (traverse _IncludedRouter wrappers)
    route_paths = _collect_route_paths(app)
    assert "/v1/chat/completions" in route_paths
    assert "/v1/models" in route_paths
    assert "/health" in route_paths
    assert "/ready" in route_paths
    assert "/metrics" in route_paths

    # RequestIDMiddleware is registered
    middleware_classes = [m.cls for m in app.user_middleware]
    assert RequestIDMiddleware in middleware_classes
    assert SafetyHeadersMiddleware in middleware_classes

    # Exception handlers are registered
    assert ProviderError in app.exception_handlers
    assert ConfigError in app.exception_handlers
    assert Exception in app.exception_handlers


# ---------------------------------------------------------------------------
# TC-FASTAPI-002: nonexistent config path raises exception with path in message.
# ---------------------------------------------------------------------------


def test_create_app_nonexistent_config_raises(config_path: str) -> None:
    """TC-FASTAPI-002: create_app with nonexistent path raises exception containing the path.

    GIVEN a nonexistent config file path
    WHEN create_app("/nonexistent/path.yaml") is called
    THEN an exception is raised
    AND the exception message contains the file path
    """
    from z_llm_safety_gateway.app import create_app

    nonexistent_path = "/nonexistent/path/to/config.yaml"

    with pytest.raises(Exception) as exc_info:
        create_app(nonexistent_path)

    assert nonexistent_path in str(exc_info.value)


# ---------------------------------------------------------------------------
# TC-FASTAPI-008: importing the app factory module does not start a server.
# ---------------------------------------------------------------------------


def test_import_app_module_no_side_effects() -> None:
    """TC-FASTAPI-008: Importing the app factory module does not start a server.

    GIVEN the z_llm_safety_gateway.app module
    WHEN it is imported
    THEN no server is started (no global app instance is created)
    AND the module exposes a create_app callable
    """
    import z_llm_safety_gateway.app as app_module

    # The module should expose create_app
    assert hasattr(app_module, "create_app")
    assert callable(app_module.create_app)

    # No global app instance should exist (factory pattern, no side effects)
    assert not hasattr(app_module, "app") or app_module.app is None
