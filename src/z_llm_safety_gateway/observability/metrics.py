"""Prometheus metrics collection for the z LLM Safety Gateway.

This module defines the metrics registry and counters/histograms/gauges that
align with DESIGN.md section 12.5:

Gateway metrics: ``safety_gateway_requests_total``,
``safety_gateway_request_duration_seconds``, ``safety_gateway_blocks_total``,
``safety_gateway_flags_total``, ``safety_gateway_active_connections``,
``safety_gateway_streaming_active``.

Detector metrics: ``safety_detector_duration_seconds``,
``safety_detector_results_total``, ``safety_detector_errors_total``,
``safety_detector_circuit_breaker_state``.

Provider metrics: ``safety_provider_requests_total``,
``safety_provider_duration_seconds``, ``safety_provider_errors_total``.

Recall metrics: ``safety_recalls_total``.

The registry is only initialized when ``observability.metrics.enabled`` is
true, so disabled deployments incur no metric-collection overhead.  Each
metric lives on a dedicated :class:`CollectorRegistry` to keep tests isolated
and avoid duplicate-registration errors across app instances.
"""

from __future__ import annotations

import threading

import structlog
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client import generate_latest as _generate_latest

logger = structlog.get_logger(__name__)


class MetricsRegistry:
    """A self-contained collection of gateway, detector, provider, and recall metrics.

    All metrics are registered on a dedicated :class:`CollectorRegistry`, so
    multiple registry instances can coexist without name collisions.
    """

    def __init__(self) -> None:
        self._registry = CollectorRegistry()

        # --- Gateway metrics (DESIGN 12.5) ---
        self.gateway_requests = Counter(
            "safety_gateway_requests_total",
            "Total requests processed",
            ["direction", "action", "model"],
            registry=self._registry,
        )
        self.gateway_duration = Histogram(
            "safety_gateway_request_duration_seconds",
            "Request processing duration in seconds",
            ["direction", "model"],
            registry=self._registry,
        )
        self.gateway_blocks = Counter(
            "safety_gateway_blocks_total",
            "Total blocked requests",
            ["direction", "category", "detector_name"],
            registry=self._registry,
        )
        self.gateway_flags = Counter(
            "safety_gateway_flags_total",
            "Total flagged requests",
            ["direction", "category", "detector_name"],
            registry=self._registry,
        )
        self.active_connections = Gauge(
            "safety_gateway_active_connections",
            "Current active connections",
            registry=self._registry,
        )
        self.streaming_active = Gauge(
            "safety_gateway_streaming_active",
            "Current active streaming connections",
            registry=self._registry,
        )

        # --- Detector metrics (DESIGN 12.5) ---
        self.detector_duration = Histogram(
            "safety_detector_duration_seconds",
            "Detector execution duration in seconds",
            ["detector_name", "direction"],
            registry=self._registry,
        )
        self.detector_results = Counter(
            "safety_detector_results_total",
            "Detector result counts",
            ["detector_name", "action"],
            registry=self._registry,
        )
        self.detector_errors = Counter(
            "safety_detector_errors_total",
            "Detector error counts",
            ["detector_name", "error_type"],
            registry=self._registry,
        )
        self.detector_circuit_breaker_state = Gauge(
            "safety_detector_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=open, 2=half-open)",
            ["detector_name"],
            registry=self._registry,
        )
        self.detector_up = Gauge(
            "safety_detector_up",
            "Whether a configured detector is loaded and healthy",
            ["detector_name", "direction", "detector_type", "policy_id"],
            registry=self._registry,
        )
        self.detector_initialization_failures = Counter(
            "safety_detector_initialization_failures_total",
            "Detector initialization failures",
            ["detector_name", "direction", "detector_type", "policy"],
            registry=self._registry,
        )
        self.gateway_degraded_requests = Counter(
            "safety_gateway_degraded_requests_total",
            "Requests continued with an explicitly degraded safety capability",
            ["direction", "detector_name"],
            registry=self._registry,
        )
        self.evidence_persistence_failures = Counter(
            "safety_evidence_persistence_failures_total",
            "Flow evidence persistence failures",
            ["sink", "error_type"],
            registry=self._registry,
        )
        self.flow_executions = Counter(
            "safety_flow_executions_total",
            "Flow execution terminal states",
            ["flow_id", "direction", "status"],
            registry=self._registry,
        )
        self.flow_duration = Histogram(
            "safety_flow_duration_seconds",
            "Flow execution duration",
            ["flow_id", "direction", "status"],
            registry=self._registry,
        )
        self.flow_node_executions = Counter(
            "safety_flow_node_executions_total",
            "Flow Node execution terminal states",
            ["flow_id", "direction", "node_id", "status", "reason_code"],
            registry=self._registry,
        )
        self.observability_sanitizations = Counter(
            "safety_observability_sanitizations_total",
            "Rejected observability attributes",
            ["field", "reason"],
            registry=self._registry,
        )

        # --- Provider metrics (DESIGN 12.5) ---
        self.provider_requests = Counter(
            "safety_provider_requests_total",
            "Total provider requests",
            ["provider", "model"],
            registry=self._registry,
        )
        self.provider_duration = Histogram(
            "safety_provider_duration_seconds",
            "Provider response duration in seconds",
            ["provider", "model"],
            registry=self._registry,
        )
        self.provider_errors = Counter(
            "safety_provider_errors_total",
            "Provider error counts",
            ["provider", "error_type"],
            registry=self._registry,
        )

        # --- Recall metrics (DESIGN 12.5) ---
        self.recalls = Counter(
            "safety_recalls_total",
            "Total post-audit recalls",
            ["category", "risk_level"],
            registry=self._registry,
        )

    def generate(self) -> bytes:
        """Render all metrics in Prometheus text exposition format."""
        return _generate_latest(self._registry)


# --------------------------------------------------------------------------- #
# Module-level enabled state and current registry
# --------------------------------------------------------------------------- #
_registry: MetricsRegistry | None = None
_enabled: bool = False
_lock = threading.Lock()


def set_enabled(enabled: bool) -> None:
    """Enable or disable metrics collection.

    When *enabled* is True a fresh :class:`MetricsRegistry` is created; when
    False the registry is dropped and collection stops.

    Args:
        enabled: Whether Prometheus metrics collection is enabled.
    """
    global _registry, _enabled
    with _lock:
        _enabled = enabled
        _registry = MetricsRegistry() if enabled else None
        logger.info(
            "metrics_enabled_changed",
            enabled=enabled,
        )


def is_enabled() -> bool:
    """Return True when metrics collection is enabled."""
    return _enabled


def generate_latest() -> bytes:
    """Render the current registry in Prometheus text format.

    Returns an empty bytes object when metrics are disabled or not initialized.
    """
    with _lock:
        reg = _registry
    if reg is None:
        return b""
    return reg.generate()


# --------------------------------------------------------------------------- #
# Recording helpers — all are no-ops when metrics are disabled
# --------------------------------------------------------------------------- #
def record_gateway_request(
    direction: str,
    action: str,
    model: str,
    duration_seconds: float,
) -> None:
    """Record a processed gateway request (counter + duration histogram)."""
    reg = _registry
    if reg is None:
        return
    reg.gateway_requests.labels(
        direction=direction, action=action, model=model
    ).inc()
    reg.gateway_duration.labels(direction=direction, model=model).observe(
        duration_seconds
    )


def record_gateway_block(
    direction: str, category: str, detector_name: str
) -> None:
    """Increment the blocked-requests counter for a detector category."""
    reg = _registry
    if reg is None:
        return
    reg.gateway_blocks.labels(
        direction=direction, category=category, detector_name=detector_name
    ).inc()


def record_gateway_flag(
    direction: str, category: str, detector_name: str
) -> None:
    """Increment the flagged-requests counter for a detector category."""
    reg = _registry
    if reg is None:
        return
    reg.gateway_flags.labels(
        direction=direction, category=category, detector_name=detector_name
    ).inc()


def set_active_connections(value: float) -> None:
    """Set the current active-connections gauge."""
    reg = _registry
    if reg is None:
        return
    reg.active_connections.set(value)


def set_streaming_active(value: float) -> None:
    """Set the current active-streaming-connections gauge."""
    reg = _registry
    if reg is None:
        return
    reg.streaming_active.set(value)


def record_detector(
    detector_name: str,
    direction: str,
    action: str,
    duration_seconds: float,
) -> None:
    """Record a detector execution (result counter + duration histogram)."""
    reg = _registry
    if reg is None:
        return
    reg.detector_results.labels(
        detector_name=detector_name, action=action
    ).inc()
    reg.detector_duration.labels(
        detector_name=detector_name, direction=direction
    ).observe(duration_seconds)


def record_detector_error(detector_name: str, error_type: str) -> None:
    """Increment the detector error counter for an error type."""
    reg = _registry
    if reg is None:
        return
    reg.detector_errors.labels(
        detector_name=detector_name, error_type=error_type
    ).inc()


def set_circuit_breaker_state(detector_name: str, state: int) -> None:
    """Set the circuit-breaker state gauge for a detector.

    Values: 0=closed, 1=open, 2=half-open.
    """
    reg = _registry
    if reg is None:
        return
    reg.detector_circuit_breaker_state.labels(detector_name=detector_name).set(
        state
    )


def set_detector_up(
    detector_name: str,
    direction: str,
    detector_type: str,
    is_up: bool,
    policy_id: str = "legacy",
) -> None:
    """Set a detector's current loaded-and-healthy state."""
    reg = _registry
    if reg is None:
        return
    reg.detector_up.labels(
        detector_name=detector_name,
        direction=direction,
        detector_type=detector_type,
        policy_id=policy_id,
    ).set(1 if is_up else 0)


def record_detector_initialization_failure(
    detector_name: str,
    direction: str,
    detector_type: str,
    policy: str,
) -> None:
    """Increment the detector initialization failure counter."""
    reg = _registry
    if reg is None:
        return
    reg.detector_initialization_failures.labels(
        detector_name=detector_name,
        direction=direction,
        detector_type=detector_type,
        policy=policy,
    ).inc()


def record_degraded_request(direction: str, detector_name: str) -> None:
    """Increment the per-detector fail-open degraded request counter."""
    reg = _registry
    if reg is None:
        return
    reg.gateway_degraded_requests.labels(
        direction=direction,
        detector_name=detector_name,
    ).inc()


def record_evidence_persistence_failure(sink: str, error_type: str) -> None:
    """Increment the bounded evidence sink failure counter."""
    reg = _registry
    if reg is None:
        return
    reg.evidence_persistence_failures.labels(
        sink=sink,
        error_type=error_type,
    ).inc()


def record_flow_execution(
    flow_id: str,
    direction: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record one bounded Flow terminal state and duration."""
    reg = _registry
    if reg is None:
        return
    reg.flow_executions.labels(
        flow_id=flow_id,
        direction=direction,
        status=status,
    ).inc()
    reg.flow_duration.labels(
        flow_id=flow_id,
        direction=direction,
        status=status,
    ).observe(duration_seconds)


def record_flow_node(
    flow_id: str,
    direction: str,
    node_id: str,
    status: str,
    reason_code: str,
) -> None:
    """Record one bounded Node terminal state."""
    reg = _registry
    if reg is None:
        return
    reg.flow_node_executions.labels(
        flow_id=flow_id,
        direction=direction,
        node_id=node_id,
        status=status,
        reason_code=reason_code,
    ).inc()


def record_observability_sanitization(field: str, reason: str) -> None:
    """Signal that an unsafe dynamic observability value was rejected."""
    reg = _registry
    if reg is None:
        return
    reg.observability_sanitizations.labels(field=field, reason=reason).inc()


def record_provider_request(
    provider: str, model: str, duration_seconds: float
) -> None:
    """Record a provider call (request counter + duration histogram)."""
    reg = _registry
    if reg is None:
        return
    reg.provider_requests.labels(provider=provider, model=model).inc()
    reg.provider_duration.labels(provider=provider, model=model).observe(
        duration_seconds
    )


def record_provider_error(provider: str, error_type: str) -> None:
    """Increment the provider error counter for an error type."""
    reg = _registry
    if reg is None:
        return
    reg.provider_errors.labels(
        provider=provider, error_type=error_type
    ).inc()


def record_recall(category: str, risk_level: str) -> None:
    """Increment the post-audit recall counter (no sensitive content)."""
    reg = _registry
    if reg is None:
        return
    reg.recalls.labels(category=category, risk_level=risk_level).inc()
