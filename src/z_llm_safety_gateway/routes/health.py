"""Health check endpoints: liveness, readiness, and metrics.

Provides three endpoints for Kubernetes-style health probing:
- GET /health  — liveness probe (always 200 if process is running)
- GET /ready   — readiness probe (200 if ready, 503 if not)
- GET /metrics — Prometheus metrics endpoint, controlled by
                 ``observability.metrics.enabled`` (404 when disabled)

The readiness state is controlled by set_ready(), called by the app factory
after configuration loading and provider client initialization complete.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from z_llm_safety_gateway.observability import metrics as observability_metrics

router = APIRouter(tags=["health"])

# Global readiness state — set by the app factory after initialization.
_ready: bool = False

# Prometheus text exposition Content-Type (see SC-PROM-001).
_METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def set_ready(is_ready: bool) -> None:
    """Set the readiness state.

    Called by the app factory after configuration is loaded and provider
    clients are initialized. Once set to True, /ready returns 200.
    """
    global _ready
    _ready = is_ready


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns 200 if the process is running.

    Does NOT check any external dependencies (providers, databases, etc.).
    A 200 response means the process is alive and can handle requests.
    """
    return {"status": "healthy"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    """Readiness probe — returns 200 if ready, 503 if not ready.

    Readiness is determined by the global _ready flag, which is set by
    the app factory after configuration loading and provider initialization.
    Returns 503 Service Unavailable when not ready so load balancers
    stop routing traffic to this instance.
    """
    if not _ready:
        response.status_code = 503
        return {"status": "not_ready"}
    return {"status": "ready"}


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint (SC-PROM-001 / SC-PROM-002).

    When ``observability.metrics.enabled`` is true, returns the current
    metrics in Prometheus text exposition format.  When disabled, returns
    404 and does not initialize any metric collection.
    """
    if not observability_metrics.is_enabled():
        return Response(status_code=404)
    return Response(
        content=observability_metrics.generate_latest(),
        media_type=_METRICS_CONTENT_TYPE,
    )
