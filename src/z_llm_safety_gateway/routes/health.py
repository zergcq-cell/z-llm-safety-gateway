"""Liveness, application-scoped readiness, and Prometheus endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response

from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatus,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.observability import metrics as observability_metrics

router = APIRouter(tags=["health"])

_METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def set_ready(app: FastAPI | bool, is_ready: bool | None = None) -> None:
    """Set readiness on an application instance.

    A one-argument call is retained as a no-op compatibility shim for code
    that only reset the former module global after tests.
    """
    if isinstance(app, bool):
        return
    if is_ready is None:
        raise TypeError("is_ready is required when setting app readiness")
    app.state.ready = is_ready


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe that deliberately checks no dependencies."""
    return {"status": "healthy"}


async def _check_detector_health(
    registry: DetectorStatusRegistry,
    status: DetectorStatus,
) -> None:
    detector = status.detector
    if detector is None:
        return
    health_check = getattr(detector, "health_check", None)
    if not callable(health_check):
        return
    try:
        healthy = await asyncio.wait_for(
            health_check(),
            timeout=status.timeout_seconds,
        )
    except asyncio.TimeoutError:
        registry.transition(
            status.direction,
            status.name,
            DetectorState.UNHEALTHY,
            reason_code=DetectorReasonCode.HEALTH_CHECK_TIMEOUT,
        )
    except Exception:
        registry.transition(
            status.direction,
            status.name,
            DetectorState.UNHEALTHY,
            reason_code=DetectorReasonCode.HEALTH_CHECK_ERROR,
        )
    else:
        registry.transition(
            status.direction,
            status.name,
            DetectorState.HEALTHY if healthy else DetectorState.UNHEALTHY,
            reason_code=None if healthy else DetectorReasonCode.HEALTH_CHECK_FAILED,
        )


async def refresh_detector_health(registry: DetectorStatusRegistry) -> None:
    """Refresh all loaded detector states concurrently with per-item bounds."""
    await asyncio.gather(
        *(
            _check_detector_health(registry, status)
            for status in registry.snapshot()
            if status.loaded
        )
    )


def _detector_summary(registry: DetectorStatusRegistry) -> dict[str, Any]:
    statuses = registry.snapshot()
    issues = registry.issues()
    degraded = registry.issues(strict=False)
    return {
        "configured": len(statuses),
        "loaded": sum(status.loaded for status in statuses),
        "healthy": sum(status.state is DetectorState.HEALTHY for status in statuses),
        "unavailable": sum(
            status.state is DetectorState.UNAVAILABLE for status in statuses
        ),
        "unhealthy": sum(status.state is DetectorState.UNHEALTHY for status in statuses),
        "degraded": len(degraded),
        "issues": [status.to_public_dict() for status in issues],
    }


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict[str, Any]:
    """Report whether this application instance can safely accept traffic."""
    registry: DetectorStatusRegistry | None = getattr(
        request.app.state, "detector_status_registry", None
    )
    if registry is None:
        is_ready = bool(getattr(request.app.state, "ready", False))
        if not is_ready:
            response.status_code = 503
        return {"status": "ready" if is_ready else "not_ready"}

    await refresh_detector_health(registry)
    strict_issues = registry.issues(strict=True)
    degraded_issues = registry.issues(strict=False)
    is_ready = not strict_issues
    request.app.state.ready = is_ready
    if not is_ready:
        response.status_code = 503
    return {
        "status": "ready" if is_ready else "not_ready",
        "degraded": bool(degraded_issues),
        "detectors": _detector_summary(registry),
    }


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics when collection is enabled."""
    if not observability_metrics.is_enabled():
        return Response(status_code=404)
    return Response(
        content=observability_metrics.generate_latest(),
        media_type=_METRICS_CONTENT_TYPE,
    )
