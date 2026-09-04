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
_HEALTH_CHECK_BATCH_SIZE = 32
_HEALTH_REFRESH_DEADLINE_SECONDS = 5.0


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
    """Refresh loaded detector states in bounded batches."""
    loaded = tuple(status for status in registry.snapshot() if status.loaded)
    for offset in range(0, len(loaded), _HEALTH_CHECK_BATCH_SIZE):
        await asyncio.gather(
            *(
                _check_detector_health(registry, status)
                for status in loaded[offset : offset + _HEALTH_CHECK_BATCH_SIZE]
            )
        )


def _detector_summary(registries: tuple[DetectorStatusRegistry, ...]) -> dict[str, Any]:
    statuses = tuple(
        status for registry in registries for status in registry.snapshot()
    )
    issues = tuple(status for registry in registries for status in registry.issues())
    degraded = tuple(
        status for registry in registries for status in registry.issues(strict=False)
    )
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
    tenant_bundles = getattr(request.app.state, "tenant_runtime_bundles", ())
    tenant_registries = tuple(
        bundle.status_registry
        for bundle in tenant_bundles
        if bundle.status_registry is not None
    )
    registries = tenant_registries or ((registry,) if registry is not None else ())
    if not registries:
        is_ready = bool(getattr(request.app.state, "ready", False))
        if not is_ready:
            response.status_code = 503
        return {"status": "ready" if is_ready else "not_ready"}

    async def refresh_all() -> None:
        # Readiness is application-wide, but bounded iteration prevents one
        # request from allocating a task for every detector in every policy.
        for item in registries:
            await refresh_detector_health(item)

    refresh_timed_out = False
    try:
        await asyncio.wait_for(
            refresh_all(), timeout=_HEALTH_REFRESH_DEADLINE_SECONDS
        )
    except asyncio.TimeoutError:
        refresh_timed_out = True
    strict_issues = tuple(
        status for item in registries for status in item.issues(strict=True)
    )
    is_ready = not strict_issues and not refresh_timed_out
    request_bundle = getattr(request.state, "_tenant_runtime_bundle", None)
    request_registry = getattr(request_bundle, "status_registry", None)
    public_registries = (
        (request_registry,) if request_registry is not None else registries
    )
    public_degraded_issues = tuple(
        status for item in public_registries for status in item.issues(strict=False)
    )
    request.app.state.ready = is_ready
    if not is_ready:
        response.status_code = 503
    return {
        "status": "ready" if is_ready else "not_ready",
        "degraded": bool(public_degraded_issues),
        "detectors": _detector_summary(public_registries),
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
