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
