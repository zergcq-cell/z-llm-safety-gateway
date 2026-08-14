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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from z_llm_safety_gateway.audit.logger import AuditLogger
from z_llm_safety_gateway.circuit_breaker.factory import build_circuit_breaker
from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.models import DetectorsConfig, _parse_duration
from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.exceptions import (
    ConfigError,
    OpenAIErrorBody,
    OpenAIErrorDetail,
    SafetyBlockError,
)
from z_llm_safety_gateway.middleware.auth import AuthMiddleware
from z_llm_safety_gateway.middleware.rate_limit import RateLimitMiddleware
from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.request_size import RequestSizeMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware
from z_llm_safety_gateway.observability import metrics as observability_metrics
from z_llm_safety_gateway.observability import tracing as observability_tracing
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle: startup and graceful shutdown.

    On shutdown, flushes audit logs, releases resources, and shuts down gRPC
    sidecar detectors (remote Shutdown + channel close).  This replaces custom
    SIGTERM/SIGINT handlers that conflicted with uvicorn's own signal
    management (v0.4.0 fix).  uvicorn triggers lifespan shutdown when it
    receives SIGTERM/SIGINT, so cleanup is guaranteed to run.
    """
    # Startup: nothing special (detectors initialized synchronously in create_app).
    yield
    # Shutdown: flush audit logs and release resources.
    audit_logger = getattr(app.state, "audit_logger", None)
    if audit_logger is not None:
        try:
            audit_logger.flush()
            audit_logger.close()
        except Exception:  # pragma: no cover - defensive, shutdown must not hang
            logger.warning("audit_shutdown_flush_failed", exc_info=True)
    # v0.5.0: shut down gRPC sidecar detectors (remote Shutdown + close).
    for detector in _all_detectors(app):
        shutdown = getattr(detector, "shutdown", None)
        if shutdown is None:
            continue
        try:
            await shutdown()
        except Exception:  # pragma: no cover - defensive
            logger.warning(
                "detector_shutdown_failed", detector=getattr(detector, "name", "?"),
                exc_info=True,
            )
    logger.info("graceful_shutdown_complete")


def _all_detectors(app: FastAPI) -> list[Any]:
    """Return all initialized detectors (input + output) from app.state."""
    detectors: list[Any] = []
    for attr in ("input_detectors", "output_detectors"):
        items = getattr(getattr(app, "state", None), attr, None) or []
        detectors.extend(items)
    return detectors


async def _init_detectors(
    registry: Any,
    input_configs: dict[str, dict[str, Any]],
    output_configs: dict[str, dict[str, Any]],
) -> tuple[list[Any], list[Any]]:
    """Initialize input and output detectors asynchronously.

    v0.5.0: detectors with ``type == "grpc"`` are created as GRPCDetector
    instances (sidecar), everything else goes through the registry (built-in
    or entry-point plugin classes).

    Returns:
        A tuple of (input_detectors_list, output_detectors_list).
    """
    input_detectors_dict = await _initialize_detectors(registry, input_configs)
    output_detectors_dict = await _initialize_detectors(registry, output_configs)
    return list(input_detectors_dict.values()), list(output_detectors_dict.values())


async def _initialize_detectors(
    registry: Any, configs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Initialize a set of detectors, creating GRPCDetector for type=grpc."""
    detectors: dict[str, Any] = {}
    for name, config in configs.items():
        try:
            if config.get("type") == "grpc":
                from z_llm_safety_gateway.plugins.grpc.client import GRPCDetector

                detector = GRPCDetector()
                await detector.initialize(config)
            else:
                detector = await registry.create_detector(name, config)
            detectors[name] = detector
        except Exception:
            # gRPC sidecar init failure is security-relevant (detector inactive):
            # log at ERROR level so operators notice the detector is not running.
            if config.get("type") == "grpc":
                logger.error(
                    "gRPC detector failed to initialize and will not run: %s",
                    name,
                    exc_info=True,
                )
            else:
                logger.exception("Failed to initialize detector: %s", name)
    return detectors


def _extract_detector_configs(
    detectors_list: Any,
    *,
    default_timeout_seconds: float,
) -> dict[str, dict[str, Any]]:
    """Extract detector configs from a DetectorsConfig input/output list.

    v0.4.0 (B-04): injects ``timeout_seconds`` (resolved from the detector's
    explicit ``timeout`` or the global ``security.timeout.detector`` default)
    and a configured ``CircuitBreaker`` instance into each detector config,
    so per-detector timeouts and circuit breakers actually take effect.

    Args:
        detectors_list: A list of DetectorConfig objects.
        default_timeout_seconds: Global default detector timeout in seconds.

    Returns:
        A dict mapping detector name to its merged config dict
        (detector-specific config + priority + on_error + timeout_seconds
        + optional CircuitBreaker instance).
    """
    configs: dict[str, dict[str, Any]] = {}
    for det in detectors_list:
        if det.enabled:
            timeout_seconds = _resolve_timeout_seconds(det, default_timeout_seconds)
            merged: dict[str, Any] = {
                **det.config,
                "type": det.type,
                "priority": det.priority,
                "on_error": det.on_error,
                "timeout_seconds": timeout_seconds,
            }
            if det.circuit_breaker is not None and det.circuit_breaker.enabled:
                merged["circuit_breaker"] = build_circuit_breaker(det.circuit_breaker)
            configs[det.name] = merged
    return configs


def _resolve_timeout_seconds(det: Any, default_timeout_seconds: float) -> float:
    """Resolve a detector's timeout to seconds.

    An explicit per-detector ``timeout`` (e.g. ``"10s"``) overrides the global
    default ``security.timeout.detector``.
    """
    if det.timeout is not None and det.timeout:
        return _parse_duration(det.timeout)
    return default_timeout_seconds


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

    # 1b. Initialize observability (Prometheus metrics + optional OTel tracing).
    observability_metrics.set_enabled(config.observability.metrics.enabled)

    # 2. Create FastAPI instance
    app = FastAPI(
        title="z LLM Safety Gateway",
        description="Open-source, modular LLM content safety gateway",
        lifespan=lifespan,
    )

    # 2b. Initialize optional OpenTelemetry tracing (best effort, off by default).
    observability_tracing.setup_tracing(config.observability.tracing, app=app)

    # 3. Register middleware (order matters in Starlette!)
    #    add_middleware() adds to the *outer* end, so we register inner-first.
    #    Final request chain (outer->inner):
    #    RequestID -> Auth -> RateLimit -> RequestSize -> SafetyHeaders
    app.add_middleware(SafetyHeadersMiddleware)
    app.add_middleware(RequestSizeMiddleware, max_request_size=config.security.max_request_size)
    app.add_middleware(RateLimitMiddleware, config=config.security.rate_limit)
    app.add_middleware(AuthMiddleware, config=config.security.auth)
    app.add_middleware(
        RequestIDMiddleware,
        header_name=config.security.request_id.header,
        generate=config.security.request_id.generate,
    )

    # 3b. CORS (optional, default off).
    from z_llm_safety_gateway.middleware.cors import build_cors_middleware_kwargs

    cors_kwargs = build_cors_middleware_kwargs(config.security.cors)
    if cors_kwargs:
        from starlette.middleware.cors import CORSMiddleware

        app.add_middleware(CORSMiddleware, **cors_kwargs)

    # 4. Create ModelRouter and store in app.state
    router = ModelRouter(config)
    app.state.router = router
    app.state.config = config

    # 5. Initialize the safety pipeline
    registry = create_default_registry()

    # v0.5.0: discover and register in-process plugin detectors (entry points).
    from z_llm_safety_gateway.plugins.loader import load_plugins

    load_plugins(registry)

    # After Pydantic validation, detectors is always a DetectorsConfig
    # (the model_validator converts legacy list format).
    detectors_cfg = config.pipeline.detectors
    assert isinstance(detectors_cfg, DetectorsConfig)

    input_configs = _extract_detector_configs(
        detectors_cfg.input,
        default_timeout_seconds=config.security.timeout.detector_seconds,
    )
    output_configs = _extract_detector_configs(
        detectors_cfg.output,
        default_timeout_seconds=config.security.timeout.detector_seconds,
    )

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
