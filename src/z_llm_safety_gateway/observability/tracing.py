"""Optional OpenTelemetry distributed tracing (DESIGN.md section 12.6).

This module is an optional integration, disabled by default.  When
``observability.tracing.enabled`` is true, it initializes a global
:class:`TracerProvider` with an OTLP exporter (MVP supports ``exporter:
otlp``), applies a ratio sampler driven by ``sample_rate``, and optionally
instruments a FastAPI app.

Because the OpenTelemetry packages are optional dependencies, all imports are
performed lazily inside the functions and guarded by ``try/except ImportError``.
When the packages are unavailable and tracing is enabled, setup logs a warning
and degrades gracefully to no-op.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

import structlog

from z_llm_safety_gateway.config.models import TracingConfig

logger = structlog.get_logger(__name__)

# SERVICE_NAME resource attribute constant (mirrors opentelemetry.sdk.resources).
_SERVICE_NAME = "service.name"
_SERVICE_NAME_VALUE = "z-llm-safety-gateway"


_enabled: bool = False
_initialized: bool = False
_provider: Any = None
_lock = threading.Lock()


def is_enabled() -> bool:
    """Return True when tracing is enabled in configuration."""
    return _enabled


def is_initialized() -> bool:
    """Return True when a TracerProvider has actually been initialized."""
    return _initialized


def setup_tracing(config: TracingConfig, app: Any | None = None) -> bool:
    """Initialize OpenTelemetry tracing from *config*.

    Args:
        config: The tracing configuration (enabled/exporter/endpoint/sample_rate).
        app: Optional FastAPI app to instrument with FastAPIInstrumentor.

    Returns:
        True if a TracerProvider was initialized, False otherwise.
    """
    global _enabled, _initialized, _provider

    if not config.enabled:
        _enabled = False
        _initialized = False
        _provider = None
        logger.info("tracing_disabled")
        return False

    if config.exporter != "otlp":
        logger.warning(
            "tracing_exporter_unsupported",
            exporter=config.exporter,
            supported="otlp",
        )
        return False

    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning("tracing_dependencies_missing")
        return False

    resource = Resource.create(
        attributes={_SERVICE_NAME: _SERVICE_NAME_VALUE}
    )
    sampler = ParentBased(TraceIdRatioBased(config.sample_rate))
    provider = TracerProvider(resource=resource, sampler=sampler)
    exporter = OTLPSpanExporter(endpoint=config.endpoint)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    otel_trace.set_tracer_provider(provider)

    if app is not None:
        _instrument_app(app)

    with _lock:
        _enabled = True
        _initialized = True
        _provider = provider

    logger.info(
        "tracing_initialized",
        exporter=config.exporter,
        sample_rate=config.sample_rate,
        endpoint=config.endpoint,
    )
    return True


def _instrument_app(app: Any) -> None:
    """Apply FastAPI auto-instrumentation to *app* (best effort)."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning("tracing_fastapi_instrumentation_missing")
        return
    FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> Any:
    """Return the tracer for the gateway's service name.

    When tracing is not initialized this returns the OpenTelemetry no-op
    tracer, so callers can safely create spans regardless of configuration.
    """
    from opentelemetry import trace as otel_trace

    return otel_trace.get_tracer(_SERVICE_NAME_VALUE, "0.4.0")


def trace_request(
    request_id: str, model: str, direction: str
) -> Any:
    """Create the root ``gateway.request`` span.

    The span carries ``request_id`` / ``model`` / ``direction`` attributes.
    """
    return get_tracer().start_as_current_span(
        "gateway.request",
        attributes={
            "request_id": request_id,
            "model": model,
            "direction": direction,
        },
    )


def trace_detector(
    detector_name: str, confidence: float, action: str
) -> Any:
    """Create a ``detector.<name>`` span with detector attributes."""
    return get_tracer().start_as_current_span(
        f"detector.{detector_name}",
        attributes={"detector_name": detector_name, "confidence": confidence, "action": action},
    )


def trace_provider(
    provider: str, model: str, streaming: bool
) -> Any:
    """Create a ``provider.call`` span with provider attributes."""
    return get_tracer().start_as_current_span(
        "provider.call",
        attributes={
            "provider": provider,
            "model": model,
            "streaming": streaming,
        },
    )


def extract_context(headers: Mapping[str, str]) -> Any:
    """Extract a W3C TraceContext from request headers.

    Returns a propagation context that can be used to continue an upstream
    trace.  When no ``traceparent`` is present, the resulting context is empty
    and a new root trace will be created.
    """
    from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator

    carrier: dict[str, str] = dict(headers)
    return TraceContextTextMapPropagator().extract(carrier)


def inject_context(context: Any, headers: dict[str, str]) -> None:
    """Inject the W3C TraceContext into a response headers dict."""
    from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator

    carrier = dict(headers)
    TraceContextTextMapPropagator().inject(carrier, context=context)
    headers.clear()
    headers.update(carrier)
