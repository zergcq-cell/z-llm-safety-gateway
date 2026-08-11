"""Health check endpoints: liveness, readiness, and metrics placeholder.

Provides three endpoints for Kubernetes-style health probing:
- GET /health  — liveness probe (always 200 if process is running)
- GET /ready   — readiness probe (200 if ready, 503 if not)
- GET /metrics — Prometheus metrics placeholder (Phase 1 returns placeholder text)

The readiness state is controlled by set_ready(), called by the app factory
after configuration loading and provider client initialization complete.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from starlette.responses import PlainTextResponse

router = APIRouter(tags=["health"])

# Global readiness state — set by the app factory after initialization.
_ready: bool = False


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


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    """Prometheus metrics placeholder.

    Phase 1 returns a placeholder string. Phase 4 will implement actual
    Prometheus metrics collection and exposition.
    """
    return "# z LLM Safety Gateway metrics placeholder\n"
