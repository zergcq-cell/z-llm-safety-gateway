"""Unit tests for OpenTelemetry tracing (TC-OTEL-001 ~ TC-OTEL-005).

Covers: disabled-by-default behavior, OTLP exporter initialization, sample
rate sampling, span structure/attributes, and W3C trace-context propagation.

OpenTelemetry is an optional dependency, so all tests mock the
``opentelemetry`` package by injecting fake modules into ``sys.modules``.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from z_llm_safety_gateway.config.models import TracingConfig
from z_llm_safety_gateway.observability import tracing as observability_tracing

# ---------------------------------------------------------------------------
# Fake OpenTelemetry namespace
# ---------------------------------------------------------------------------


class FakeTraceModule:
    """Fake ``opentelemetry.trace`` module."""

    def __init__(self, tracer: FakeTracer) -> None:
        self.provider: Any = None
        self.tracer = tracer

    def set_tracer_provider(self, provider: Any) -> None:
        self.provider = provider

    def get_tracer(self, *args: Any, **kwargs: Any) -> Any:
        return self.tracer


class FakeTracerProvider:
    """Fake ``opentelemetry.sdk.trace.TracerProvider``."""

    def __init__(self, resource: Any = None, sampler: Any = None) -> None:
        self.resource = resource
        self.sampler = sampler
        self.processors: list[Any] = []

    def add_span_processor(self, processor: Any) -> None:
        self.processors.append(processor)


class FakeResource:
    """Fake ``opentelemetry.sdk.resources.Resource``."""

    created_attributes: dict[str, str] | None = None

    @classmethod
    def create(cls, attributes: dict[str, str] | None = None) -> FakeResource:
        cls.created_attributes = attributes or {}
        return cls()


class FakeTraceIdRatioBased:
    """Fake ratio sampler that records the configured ratio."""

    def __init__(self, ratio: float) -> None:
        self.ratio = ratio


class FakeParentBased:
    """Fake parent-based sampler wrapping an inner ratio sampler."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner


class FakeOTLPSpanExporter:
    """Fake OTLP span exporter that records the endpoint."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint


class FakeBatchSpanProcessor:
    """Fake batch span processor that records its exporter."""

    def __init__(self, exporter: Any) -> None:
        self.exporter = exporter


class FakeFastAPIInstrumentor:
    """Fake FastAPI auto-instrumentor."""

    instrumented: list[Any] = []

    @classmethod
    def instrument_app(cls, app: Any) -> None:
        cls.instrumented.append(app)


class _FakeSpanEvent:
    def __init__(self, kind: str, name: str, attributes: Any, depth: int) -> None:
        self.kind = kind
        self.name = name
        self.attributes = attributes
        self.depth = depth


class _SpanCtx:
    """Context manager mimicking ``start_as_current_span``."""

    def __init__(self, tracer: FakeTracer, name: str, attributes: Any) -> None:
        self.tracer = tracer
        self.name = name
        self.attributes = attributes
        self.depth = 0

    def __enter__(self) -> _SpanCtx:
        self.depth = self.tracer.depth
        self.tracer.depth += 1
        self.tracer.events.append(
            _FakeSpanEvent("start", self.name, self.attributes, self.depth)
        )
        return self

    def __exit__(self, *args: Any) -> bool:
        self.tracer.depth -= 1
        self.tracer.events.append(_FakeSpanEvent("end", self.name, None, self.depth))
        return False


class FakeTracer:
    """Fake tracer that records span starts/ends and nesting depth."""

    def __init__(self) -> None:
        self.events: list[_FakeSpanEvent] = []
        self.depth = 0

    def start_as_current_span(self, name: str, attributes: Any = None) -> _SpanCtx:
        return _SpanCtx(self, name, attributes or {})


class FakePropagator:
    """Fake W3C ``TraceContextTextMapPropagator``.

    State is recorded at class level so instances created internally by the
    module under test are still observable.
    """

    extract_carrier: dict[str, str] | None = None
    inject_carrier: dict[str, str] | None = None
    inject_context: Any = None

    def extract(self, carrier: dict[str, str]) -> Any:
        FakePropagator.extract_carrier = carrier
        return {"_ctx": carrier.get("traceparent", "new-root")}

    def inject(self, carrier: dict[str, str], context: Any = None) -> None:
        FakePropagator.inject_carrier = carrier
        FakePropagator.inject_context = context
        carrier["traceparent"] = "00-1111-2222-01"


class FakeOTEL:
    """Namespace holding all fake OpenTelemetry objects."""

    def __init__(self) -> None:
        self.tracer = FakeTracer()
        self.trace = FakeTraceModule(self.tracer)
        self.TracerProvider = FakeTracerProvider
        self.Resource = FakeResource
        self.TraceIdRatioBased = FakeTraceIdRatioBased
        self.ParentBased = FakeParentBased
        self.OTLPSpanExporter = FakeOTLPSpanExporter
        self.BatchSpanProcessor = FakeBatchSpanProcessor
        self.FastAPIInstrumentor = FakeFastAPIInstrumentor
        self.Propagator = FakePropagator


_OTEL_MODULE_NAMES = [
    "opentelemetry",
    "opentelemetry.trace",
    "opentelemetry.sdk",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.sdk.trace.sampling",
    "opentelemetry.sdk.resources",
    "opentelemetry.exporter",
    "opentelemetry.exporter.otlp",
    "opentelemetry.exporter.otlp.proto",
    "opentelemetry.exporter.otlp.proto.grpc",
    "opentelemetry.exporter.otlp.proto.grpc.trace_exporter",
    "opentelemetry.propagators",
    "opentelemetry.propagators.tracecontext",
    "opentelemetry.instrumentation",
    "opentelemetry.instrumentation.fastapi",
]


@pytest.fixture
def fake_otel() -> FakeOTEL:
    """Install fake OpenTelemetry modules into sys.modules for the test."""
    fake = FakeOTEL()

    opentelemetry = types.ModuleType("opentelemetry")
    opentelemetry.trace = fake.trace

    sdk = types.ModuleType("opentelemetry.sdk")
    trace_mod = types.ModuleType("opentelemetry.sdk.trace")
    export_mod = types.ModuleType("opentelemetry.sdk.trace.export")
    sampling_mod = types.ModuleType("opentelemetry.sdk.trace.sampling")
    resources_mod = types.ModuleType("opentelemetry.sdk.resources")
    trace_mod.TracerProvider = fake.TracerProvider
    export_mod.BatchSpanProcessor = fake.BatchSpanProcessor
    sampling_mod.ParentBased = fake.ParentBased
    sampling_mod.TraceIdRatioBased = fake.TraceIdRatioBased
    resources_mod.Resource = fake.Resource
    sdk.trace = trace_mod
    trace_mod.export = export_mod
    trace_mod.sampling = sampling_mod
    sdk.resources = resources_mod
    opentelemetry.sdk = sdk

    exporter = types.ModuleType("opentelemetry.exporter")
    otlp = types.ModuleType("opentelemetry.exporter.otlp")
    proto = types.ModuleType("opentelemetry.exporter.otlp.proto")
    grpc = types.ModuleType("opentelemetry.exporter.otlp.proto.grpc")
    trace_exporter = types.ModuleType(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
    )
    trace_exporter.OTLPSpanExporter = fake.OTLPSpanExporter
    grpc.trace_exporter = trace_exporter
    proto.grpc = grpc
    otlp.proto = proto
    exporter.otlp = otlp
    opentelemetry.exporter = exporter

    propagators = types.ModuleType("opentelemetry.propagators")
    tracecontext = types.ModuleType("opentelemetry.propagators.tracecontext")
    tracecontext.TraceContextTextMapPropagator = fake.Propagator
    propagators.tracecontext = tracecontext
    opentelemetry.propagators = propagators

    instrumentation = types.ModuleType("opentelemetry.instrumentation")
    fastapi = types.ModuleType("opentelemetry.instrumentation.fastapi")
    fastapi.FastAPIInstrumentor = fake.FastAPIInstrumentor
    instrumentation.fastapi = fastapi
    opentelemetry.instrumentation = instrumentation

    modules = {
        "opentelemetry": opentelemetry,
        "opentelemetry.trace": fake.trace,
        "opentelemetry.sdk": sdk,
        "opentelemetry.sdk.trace": trace_mod,
        "opentelemetry.sdk.trace.export": export_mod,
        "opentelemetry.sdk.trace.sampling": sampling_mod,
        "opentelemetry.sdk.resources": resources_mod,
        "opentelemetry.exporter": exporter,
        "opentelemetry.exporter.otlp": otlp,
        "opentelemetry.exporter.otlp.proto": proto,
        "opentelemetry.exporter.otlp.proto.grpc": grpc,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": trace_exporter,
        "opentelemetry.propagators": propagators,
        "opentelemetry.propagators.tracecontext": tracecontext,
        "opentelemetry.instrumentation": instrumentation,
        "opentelemetry.instrumentation.fastapi": fastapi,
    }

    saved: dict[str, Any] = {}
    for name in modules:
        saved[name] = sys.modules.get(name)
        sys.modules[name] = modules[name]

    yield fake

    for name in modules:
        if saved[name] is not None:
            sys.modules[name] = saved[name]
        else:
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def reset_tracing_state() -> None:
    """Reset the tracing module to disabled after each test."""
    yield
    observability_tracing.setup_tracing(TracingConfig(enabled=False))


# ---------------------------------------------------------------------------
# TC-OTEL-001 (SC-OTEL-001): disabled by default -> no TracerProvider init
# ---------------------------------------------------------------------------


def test_tracing_disabled_by_default_does_not_initialize(fake_otel: FakeOTEL) -> None:
    """TC-OTEL-001: tracing.enabled=false does not initialize a TracerProvider.

    GIVEN observability.tracing.enabled=false
    WHEN setup_tracing is called with the default (disabled) config
    THEN no TracerProvider is initialized
    AND nothing is exported.
    """
    result = observability_tracing.setup_tracing(TracingConfig(enabled=False))

    assert result is False
    assert observability_tracing.is_initialized() is False
    assert observability_tracing.is_enabled() is False
    # The fake provider must remain unset: no exporter was created.
    assert fake_otel.trace.provider is None


# ---------------------------------------------------------------------------
# TC-OTEL-002 (SC-OTEL-002): enabled + otlp -> TracerProvider initialized
# ---------------------------------------------------------------------------


def test_tracing_enabled_otlp_initializes_provider_and_exporter(
    fake_otel: FakeOTEL,
) -> None:
    """TC-OTEL-002: tracing.enabled=true + exporter=otlp initializes provider.

    GIVEN tracing.enabled=true, exporter=otlp, endpoint=http://otel-collector:4317
    WHEN setup_tracing is called
    THEN a global TracerProvider is initialized
    AND the OTLP exporter points to the configured endpoint.
    """
    config = TracingConfig(
        enabled=True,
        exporter="otlp",
        endpoint="http://otel-collector:4317",
        sample_rate=0.1,
    )

    result = observability_tracing.setup_tracing(config)

    assert result is True
    assert observability_tracing.is_initialized() is True
    assert observability_tracing.is_enabled() is True
    assert isinstance(fake_otel.trace.provider, FakeTracerProvider)
    assert fake_otel.trace.provider.processors
    exporter = fake_otel.trace.provider.processors[0].exporter
    assert exporter.endpoint == "http://otel-collector:4317"


def test_tracing_unsupported_exporter_is_rejected(fake_otel: FakeOTEL) -> None:
    """Only the 'otlp' exporter is supported in the MVP."""
    config = TracingConfig(enabled=True, exporter="jaeger", sample_rate=0.1)

    result = observability_tracing.setup_tracing(config)

    assert result is False
    assert observability_tracing.is_initialized() is False
    assert fake_otel.trace.provider is None


# ---------------------------------------------------------------------------
# TC-OTEL-003 (SC-OTEL-003): sample_rate drives the sampler
# ---------------------------------------------------------------------------


def test_tracing_sample_rate_configures_sampler(fake_otel: FakeOTEL) -> None:
    """TC-OTEL-003: sample_rate is applied via the ratio sampler.

    GIVEN tracing.enabled=true and sample_rate=0.1
    WHEN setup_tracing is called
    THEN the sampler is a ParentBased(TraceIdRatioBased(0.1))
    AND un-sampled requests are not exported (provider uses the sampler).
    """
    config = TracingConfig(enabled=True, exporter="otlp", sample_rate=0.1)

    observability_tracing.setup_tracing(config)

    provider = fake_otel.trace.provider
    assert isinstance(provider.sampler, FakeParentBased)
    assert isinstance(provider.sampler.inner, FakeTraceIdRatioBased)
    assert provider.sampler.inner.ratio == pytest.approx(0.1)


def test_tracing_sample_rate_defaults_to_01() -> None:
    """TracingConfig.sample_rate SHALL default to 0.1."""
    config = TracingConfig(enabled=True)
    assert config.sample_rate == 0.1


# ---------------------------------------------------------------------------
# TC-OTEL-004 (SC-OTEL-004): span structure and attributes
# ---------------------------------------------------------------------------


def test_tracing_span_structure_and_attributes(fake_otel: FakeOTEL) -> None:
    """TC-OTEL-004: gateway.request root + detector/provider child spans.

    GIVEN tracing enabled and a request spanning detection and provider calls
    WHEN trace_request / trace_detector / trace_provider are used
    THEN a gateway.request root span carries request_id/model/direction
    AND detector.* and provider.call child spans carry their attributes.
    """
    with observability_tracing.trace_request("req-1", "gpt-4", "input"):
        with observability_tracing.trace_detector("prompt_injection", 0.9, "block"):
            pass
        with observability_tracing.trace_provider("openai", "gpt-4", True):
            pass

    events = fake_otel.tracer.events
    starts = [e for e in events if e.kind == "start"]

    root = starts[0]
    assert root.name == "gateway.request"
    assert root.depth == 0
    assert root.attributes["request_id"] == "req-1"
    assert root.attributes["model"] == "gpt-4"
    assert root.attributes["direction"] == "input"

    detector = next(e for e in starts if e.name == "detector.prompt_injection")
    assert detector.depth == 1
    assert detector.attributes["detector_name"] == "prompt_injection"
    assert detector.attributes["confidence"] == 0.9
    assert detector.attributes["action"] == "block"

    provider = next(e for e in starts if e.name == "provider.call")
    assert provider.depth == 1
    assert provider.attributes["provider"] == "openai"
    assert provider.attributes["model"] == "gpt-4"
    assert provider.attributes["streaming"] is True


# ---------------------------------------------------------------------------
# TC-OTEL-005 (SC-OTEL-005): W3C trace context propagation
# ---------------------------------------------------------------------------


def test_tracing_w3c_context_propagation(fake_otel: FakeOTEL) -> None:
    """TC-OTEL-005: W3C traceparent is extracted and injected.

    GIVEN a request carrying a traceparent header
    WHEN extract_context is called
    THEN the gateway continues the client trace context
    AND inject_context propagates traceparent into the response headers.
    """
    headers = {"traceparent": "00-aaaabbbb-ccccdddd-01"}
    context = observability_tracing.extract_context(headers)

    assert FakePropagator.extract_carrier == headers
    assert context == {"_ctx": "00-aaaabbbb-ccccdddd-01"}

    response_headers: dict[str, str] = {}
    observability_tracing.inject_context(context, response_headers)
    assert FakePropagator.inject_context == context
    assert response_headers["traceparent"] == "00-1111-2222-01"


def test_tracing_without_client_context_creates_new_root(
    fake_otel: FakeOTEL,
) -> None:
    """TC-OTEL-005: no client context -> new root trace (empty extract)."""
    context = observability_tracing.extract_context({})
    assert FakePropagator.extract_carrier == {}
    assert context == {"_ctx": "new-root"}
