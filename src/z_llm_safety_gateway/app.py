"""FastAPI application factory for the z LLM Safety Gateway.

The :func:`create_app` factory loads configuration, registers middleware and
routes, creates the ModelRouter, initializes the safety pipeline (detectors
and engine), and wires up global exception handlers that produce
OpenAI-compatible error responses.

Importing this module does NOT start a server or create an app instance —
:func:`create_app` must be called explicitly.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from z_llm_safety_gateway.audit.logger import AuditLogger
from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.models import DetectorsConfig
from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.exceptions import (
    ConfigError,
    OpenAIErrorBody,
    OpenAIErrorDetail,
    SafetyBlockError,
)
from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware
from z_llm_safety_gateway.pipeline import FlagEscalationRule, PipelineEngine
from z_llm_safety_gateway.post_audit.audit import PostAuditRunner
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.router import ModelRouter
from z_llm_safety_gateway.recall.webhook import WebhookRecall
from z_llm_safety_gateway.routes.chat import router as chat_router
from z_llm_safety_gateway.routes.health import router as health_router
from z_llm_safety_gateway.routes.health import set_ready
from z_llm_safety_gateway.routes.models import router as models_router

logger = structlog.get_logger()


async def _init_detectors(
    registry: Any,
    input_configs: dict[str, dict[str, Any]],
    output_configs: dict[str, dict[str, Any]],
) -> tuple[list[Any], list[Any]]:
    """Initialize input and output detectors asynchronously.

    Returns:
        A tuple of (input_detectors_list, output_detectors_list).
    """
    input_detectors_dict = await registry.initialize_all(input_configs)
    output_detectors_dict = await registry.initialize_all(output_configs)
    return list(input_detectors_dict.values()), list(output_detectors_dict.values())


def _extract_detector_configs(
    detectors_list: Any,
) -> dict[str, dict[str, Any]]:
    """Extract detector configs from a DetectorsConfig input/output list.

    Args:
        detectors_list: A list of DetectorConfig objects.

    Returns:
        A dict mapping detector name to its merged config dict
        (detector-specific config + priority + on_error).
    """
    configs: dict[str, dict[str, Any]] = {}
    for det in detectors_list:
        if det.enabled:
            configs[det.name] = {
                **det.config,
                "priority": det.priority,
                "on_error": det.on_error,
            }
    return configs


def create_app(config_path: str) -> FastAPI:
    """Create and configure a FastAPI application instance.

    Steps:
        1. Load YAML configuration from *config_path*.
        2. Create a FastAPI instance.
        3. Register middleware (SafetyHeaders inner, RequestID outer).
        4. Create a ModelRouter and store it in ``app.state``.
        5. Initialize the safety pipeline (detectors + engine) and store in
           ``app.state``.
        6. Register route groups (health, chat, models).
        7. Register global exception handlers (ProviderError, ConfigError,
           SafetyBlockError, Exception).
        8. Set the readiness flag to True.
        9. Return the configured application.

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

    # 5. Initialize the safety pipeline
    registry = create_default_registry()

    # After Pydantic validation, detectors is always a DetectorsConfig
    # (the model_validator converts legacy list format).
    detectors_cfg = config.pipeline.detectors
    assert isinstance(detectors_cfg, DetectorsConfig)

    input_configs = _extract_detector_configs(detectors_cfg.input)
    output_configs = _extract_detector_configs(detectors_cfg.output)

    # Initialize detectors eagerly (asyncio.run works because create_app
    # is called outside of a running event loop).
    input_detectors, output_detectors = asyncio.run(
        _init_detectors(registry, input_configs, output_configs)
    )

    # Create pipeline engine
    short_circuit_on = config.pipeline.short_circuit_on
    flag_escalation_rule: FlagEscalationRule | None = None
    if (
        config.pipeline.flag_escalation is not None
        and config.pipeline.flag_escalation.enabled
        and config.pipeline.flag_escalation.rule
    ):
        flag_escalation_rule = FlagEscalationRule(config.pipeline.flag_escalation.rule)

    engine = PipelineEngine(
        short_circuit_on=short_circuit_on,
        flag_escalation=flag_escalation_rule,
    )

    app.state.input_detectors = input_detectors
    app.state.output_detectors = output_detectors
    app.state.input_detector_configs = input_configs
    app.state.output_detector_configs = output_configs
    app.state.pipeline_engine = engine

    logger.info(
        "pipeline_initialized",
        input_detectors=len(input_detectors),
        output_detectors=len(output_detectors),
        short_circuit_on=short_circuit_on,
    )

    # 5b. Initialize v0.3.0 components: audit logger, streaming config,
    #     post-audit runner, and webhook recall channels.
    audit_cfg = config.audit
    audit_logger = AuditLogger(
        store_content=audit_cfg.store_content,
        sanitize_logs=audit_cfg.sanitize_logs,
        file_enabled=audit_cfg.file.enabled,
        log_dir=audit_cfg.file.path,
        stdout_enabled=audit_cfg.stdout,
        enabled=audit_cfg.enabled,
        rotation=audit_cfg.file.rotation,
        retention_days=audit_cfg.file.retention_days,
    )
    app.state.audit_logger = audit_logger
    app.state.audit_config = audit_cfg

    streaming_cfg = config.pipeline.streaming
    app.state.streaming_config = streaming_cfg

    output_detection_cfg = config.pipeline.output_detection
    app.state.output_detection_config = output_detection_cfg

    # Post-audit runner for streaming responses (reuses pipeline engine).
    post_audit_runner = PostAuditRunner(
        engine=engine,
        output_detectors=output_detectors,
        detector_configs=output_configs,
    )
    app.state.post_audit_runner = post_audit_runner

    # Webhook recall for streaming post-audit (if webhook configured).
    streaming_webhook = WebhookRecall(
        webhook_url=streaming_cfg.recall.webhook_url,
        webhook_auth_header=streaming_cfg.recall.webhook_auth_header,
    )
    app.state.streaming_webhook_recall = streaming_webhook

    # Webhook recall for non-streaming async output detection.
    output_webhook = WebhookRecall(
        webhook_url=output_detection_cfg.recall.webhook_url,
        webhook_auth_header=output_detection_cfg.recall.webhook_auth_header,
    )
    app.state.output_webhook_recall = output_webhook

    logger.info(
        "v03_components_initialized",
        audit_enabled=audit_cfg.enabled,
        streaming_mode=streaming_cfg.mode,
        output_detection_mode=output_detection_cfg.mode,
    )

    # 6. Register routes
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(models_router)

    # 7. Register exception handlers

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

    @app.exception_handler(SafetyBlockError)
    async def handle_safety_block(
        request: Request, exc: SafetyBlockError
    ) -> JSONResponse:
        """Convert SafetyBlockError into an OpenAI-compatible JSON response
        with a safety extension field.

        - direction == "input" → HTTP 400, code: safety_input_blocked
        - direction == "output" → HTTP 422, code: safety_output_blocked
        """
        if exc.direction == "input":
            status_code = 400
            code = "safety_input_blocked"
        else:
            status_code = 422
            code = "safety_output_blocked"

        safety_info = {
            "detector_name": exc.detector_name,
            "category": exc.category,
            "risk_level": exc.risk_level,
            "confidence": exc.confidence,
            "message": exc.message,
            "direction": exc.direction,
        }

        body: dict[str, Any] = {
            "error": {
                "message": exc.message,
                "type": "safety_block",
                "code": code,
                "safety": safety_info,
            }
        }
        return JSONResponse(status_code=status_code, content=body)

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

    # 8. Set readiness state
    set_ready(True)

    # 9. Return the configured app
    return app
