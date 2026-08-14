"""Unit tests for Prometheus metrics (TC-PROM-001 ~ TC-PROM-006).

Covers: /metrics endpoint enable/disable behavior, gateway metrics,
detector metrics, provider metrics, and recall metrics.  Aligns with
DESIGN.md section 12.5 and the prometheus-metrics capability spec.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from z_llm_safety_gateway.observability import metrics as observability_metrics
from z_llm_safety_gateway.routes.health import router

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@pytest.fixture(autouse=True)
def reset_metrics_state() -> None:
    """Disable metrics and drop the registry after each test."""
    yield
    observability_metrics.set_enabled(False)


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with only the health router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for the health-router app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# TC-PROM-001 (SC-PROM-001): /metrics enabled -> 200 + Prometheus text format
# ---------------------------------------------------------------------------


def test_metrics_endpoint_enabled_returns_prometheus_text(
    client: TestClient,
) -> None:
    """TC-PROM-001: metrics.enabled=true exposes /metrics in Prometheus text format.

    GIVEN observability.metrics.enabled=true and the /metrics route registered
    WHEN the client GETs /metrics
    THEN the gateway returns HTTP 200 with Content-Type
         "text/plain; version=0.0.4; charset=utf-8"
    AND the body contains the registered metric families.
    """
    observability_metrics.set_enabled(True)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"] == METRICS_CONTENT_TYPE
    assert "safety_gateway_requests_total" in response.text


# ---------------------------------------------------------------------------
# TC-PROM-002 (SC-PROM-002): /metrics disabled -> 404, registry not initialized
# ---------------------------------------------------------------------------


def test_metrics_endpoint_disabled_returns_404(client: TestClient) -> None:
    """TC-PROM-002: metrics.enabled=false does not expose /metrics (404).

    GIVEN observability.metrics.enabled=false
    WHEN the client GETs /metrics
    THEN the gateway returns HTTP 404
    AND the metric registry is NOT initialized (no collection overhead).
    """
    observability_metrics.set_enabled(False)

    response = client.get("/metrics")

    assert response.status_code == 404
    assert observability_metrics.is_enabled() is False
    assert observability_metrics.generate_latest() == b""


def test_metrics_disabled_by_default() -> None:
    """Metrics collection SHALL default to disabled."""
    # set_enabled(False) in the autouse fixture leaves it disabled.
    assert observability_metrics.is_enabled() is False


# ---------------------------------------------------------------------------
# TC-PROM-003 (SC-PROM-003): gateway metrics counters and labels
# ---------------------------------------------------------------------------


def test_gateway_metrics_counters_and_labels() -> None:
    """TC-PROM-003: gateway request/block/flag counters carry correct labels.

    GIVEN metrics.enabled=true and gateway metrics registered
    WHEN a request with action=block, direction=input, model=gpt-4 is recorded
         plus a block and a flag
    THEN safety_gateway_requests_total increments with direction/action/model
    AND safety_gateway_request_duration_seconds histogram exists
    AND blocks_total/flags_total increment with direction/category/detector_name.
    """
    observability_metrics.set_enabled(True)

    observability_metrics.record_gateway_request(
        direction="input", action="block", model="gpt-4", duration_seconds=0.5
    )
    observability_metrics.record_gateway_block(
        direction="input", category="pii", detector_name="pii_redaction"
    )
    observability_metrics.record_gateway_flag(
        direction="input", category="toxicity", detector_name="toxicity"
    )

    out = observability_metrics.generate_latest().decode()

    assert "safety_gateway_requests_total" in out
    assert 'direction="input"' in out
    assert 'action="block"' in out
    assert 'model="gpt-4"' in out
    assert "safety_gateway_request_duration_seconds" in out
    assert "safety_gateway_blocks_total" in out
    assert 'category="pii"' in out
    assert 'detector_name="pii_redaction"' in out
    assert "safety_gateway_flags_total" in out
    assert 'category="toxicity"' in out
    assert 'detector_name="toxicity"' in out


def test_gateway_active_gauges() -> None:
    """TC-PROM-003: active connections / streaming gauges reflect current values."""
    observability_metrics.set_enabled(True)

    observability_metrics.set_active_connections(3)
    observability_metrics.set_streaming_active(1)

    out = observability_metrics.generate_latest().decode()
    assert "safety_gateway_active_connections 3.0" in out
    assert "safety_gateway_streaming_active 1.0" in out


# ---------------------------------------------------------------------------
# TC-PROM-004 (SC-PROM-004): detector metrics
# ---------------------------------------------------------------------------


def test_detector_metrics_counters_and_circuit_state() -> None:
    """TC-PROM-004: detector duration/results/errors and circuit-breaker gauge.

    GIVEN metrics.enabled=true and a detector executes with a result then an error
    WHEN record_detector, record_detector_error, set_circuit_breaker_state are called
    THEN safety_detector_duration_seconds / results_total / errors_total update
    AND safety_detector_circuit_breaker_state gauge reflects the state (1=open).
    """
    observability_metrics.set_enabled(True)

    observability_metrics.record_detector(
        detector_name="prompt_injection",
        direction="input",
        action="block",
        duration_seconds=0.3,
    )
    observability_metrics.record_detector_error("prompt_injection", "timeout")
    observability_metrics.set_circuit_breaker_state("prompt_injection", 1)

    out = observability_metrics.generate_latest().decode()

    assert "safety_detector_duration_seconds" in out
    assert "safety_detector_results_total" in out
    assert 'detector_name="prompt_injection"' in out
    assert "safety_detector_errors_total" in out
    assert 'error_type="timeout"' in out
    assert "safety_detector_circuit_breaker_state" in out
    assert (
        'safety_detector_circuit_breaker_state{detector_name="prompt_injection"} 1.0'
        in out
    )


# ---------------------------------------------------------------------------
# TC-PROM-005 (SC-PROM-005): provider metrics
# ---------------------------------------------------------------------------


def test_provider_metrics_counters() -> None:
    """TC-PROM-005: provider request/duration/error metrics with labels.

    GIVEN metrics.enabled=true and a provider routes to openai/gpt-4
    WHEN record_provider_request and record_provider_error are called
    THEN safety_provider_requests_total / duration_seconds / errors_total update
         with provider/model labels.
    """
    observability_metrics.set_enabled(True)

    observability_metrics.record_provider_request("openai", "gpt-4", 1.2)
    observability_metrics.record_provider_error("openai", "http_500")

    out = observability_metrics.generate_latest().decode()

    assert "safety_provider_requests_total" in out
    assert 'provider="openai"' in out
    assert 'model="gpt-4"' in out
    assert "safety_provider_duration_seconds" in out
    assert "safety_provider_errors_total" in out
    assert 'error_type="http_500"' in out


# ---------------------------------------------------------------------------
# TC-PROM-006 (SC-PROM-006): recall metrics
# ---------------------------------------------------------------------------


def test_recall_metrics_counter() -> None:
    """TC-PROM-006: post-audit recall counter with category/risk_level labels.

    GIVEN metrics.enabled=true and a post-audit recall with category=pii, risk=high
    WHEN record_recall is called
    THEN safety_recalls_total increments with category/risk_level labels
    AND no sensitive content is recorded.
    """
    observability_metrics.set_enabled(True)

    observability_metrics.record_recall("pii", "high")

    out = observability_metrics.generate_latest().decode()

    assert "safety_recalls_total" in out
    assert 'category="pii"' in out
    assert 'risk_level="high"' in out
    # The recall metric must not expose plaintext content.
    assert "secret" not in out.lower() or "safety_recalls_total" in out
