"""FastAPI application factory for the z LLM Safety Gateway.

The :func:`create_app` factory loads configuration, registers middleware and
routes, creates the ModelRouter, and wires up global exception handlers that
produce OpenAI-compatible error responses.

Importing this module does NOT start a server or create an app instance —
:func:`create_app` must be called explicitly.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.exceptions import (
    ConfigError,
    OpenAIErrorBody,
    OpenAIErrorDetail,
)
from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.router import ModelRouter
from z_llm_safety_gateway.routes.chat import router as chat_router
from z_llm_safety_gateway.routes.health import router as health_router
from z_llm_safety_gateway.routes.health import set_ready
from z_llm_safety_gateway.routes.models import router as models_router

logger = structlog.get_logger()


def create_app(config_path: str) -> FastAPI:
    """Create and configure a FastAPI application instance.

    Steps:
        1. Load YAML configuration from *config_path*.
        2. Create a FastAPI instance.
        3. Register middleware (SafetyHeaders inner, RequestID outer).
        4. Create a ModelRouter and store it in ``app.state``.
        5. Register route groups (health, chat, models).
        6. Register global exception handlers (ProviderError, ConfigError, Exception).
        7. Set the readiness flag to True.
        8. Return the configured application.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A configured :class:`FastAPI` instance.

    Raises:
        ConfigError: If the config file is missing or invalid.
        ConfigValidationError: If Pydantic or cross-field validation fails.
    """
    # 1. Load configuration
    config = load_config(config_path)

    # 2. Create FastAPI instance
    app = FastAPI(
        title="z LLM Safety Gateway",
        description="Open-source, modular LLM content safety gateway",
    )

    # 3. Register middleware (order matters in Starlette!)
    #    SafetyHeaders added first → inner (processes response first)
    #    RequestID   added second  → outer (processes request first, response last)
    app.add_middleware(SafetyHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # 4. Create ModelRouter and store in app.state
    router = ModelRouter(config)
    app.state.router = router
    app.state.config = config

    # 5. Register routes
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(models_router)

    # 6. Register exception handlers

    @app.exception_handler(ProviderError)
    async def handle_provider_error(
        request: Request, exc: ProviderError
    ) -> JSONResponse:
        """Convert ProviderError into an OpenAI-compatible JSON response.

        - status_code == 404 → HTTP 404, type: invalid_request_error,
          code: model_not_found
        - Other status codes → HTTP 502, type: provider_error
        """
        if exc.status_code == 404:
            body = OpenAIErrorBody(
                error=OpenAIErrorDetail(
                    message=exc.message,
                    type="invalid_request_error",
                    code="model_not_found",
                )
            )
            return JSONResponse(status_code=404, content=body.model_dump())

        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message=exc.message,
                type="provider_error",
                code=f"http_{exc.status_code}" if exc.status_code else None,
            )
        )
        return JSONResponse(status_code=502, content=body.model_dump())

    @app.exception_handler(ConfigError)
    async def handle_config_error(
        request: Request, exc: ConfigError
    ) -> JSONResponse:
        """Convert ConfigError into a 500 internal_error without exposing details."""
        logger.error("config_error_during_request", error=str(exc))
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Internal configuration error",
                type="internal_error",
                code="config_error",
            )
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    @app.exception_handler(Exception)
    async def handle_generic_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler: log full details, return generic 500 to client."""
        logger.error(
            "unhandled_exception",
            error=str(exc),
            exc_info=exc,
            error_type=type(exc).__name__,
        )
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Internal server error",
                type="internal_error",
            )
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    # 7. Set readiness state
    set_ready(True)

    # 8. Return the configured app
    return app
