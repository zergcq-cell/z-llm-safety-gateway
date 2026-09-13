"""Resolve trusted tenant identity to one request-scoped runtime policy."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.observability import metrics
from z_llm_safety_gateway.observability.tenant import bound_tenant_observation
from z_llm_safety_gateway.tenancy.observation import (
    TenantObservationContext,
    build_tenant_observation_context,
)
from z_llm_safety_gateway.tenancy.policy import (
    TenantPolicyResolver,
    TenantPolicyUnavailableError,
)

logger = structlog.get_logger(__name__)


class TenantPolicyResolutionMiddleware(BaseHTTPMiddleware):
    """Resolve policy after authentication and before downstream admission."""

    def __init__(self, app: ASGIApp, resolver: TenantPolicyResolver) -> None:
        super().__init__(app)
        self._resolver = resolver

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        tenant_context = getattr(request.state, "tenant_context", None)
        try:
            resolution = self._resolver.resolve(tenant_context)
        except TenantPolicyUnavailableError:
            logger.error("tenant_policy_unavailable")
            metrics.record_tenant_event(
                TenantObservationContext.unattributed(),
                "policy_unavailable",
                runtime=getattr(request.app.state, "metrics_runtime", None),
            )
            return self._unavailable_response()

        if resolution is None:
            request.state.tenant_policy_context = None
            request.state._tenant_runtime_bundle = None
        else:
            request.state.tenant_policy_context = resolution.context
            request.state._tenant_runtime_bundle = resolution.bundle
        if self._resolver.enabled:
            try:
                request.state.tenant_observation_context = build_tenant_observation_context(
                    tenant_context,
                    getattr(request.state, "tenant_policy_context", None),
                )
            except ValueError:
                logger.error("tenant_context_invalid")
                metrics.record_tenant_event(
                    TenantObservationContext.unattributed(),
                    "tenant_context_invalid",
                    runtime=getattr(request.app.state, "metrics_runtime", None),
                )
                return self._unavailable_response()
        else:
            request.state.tenant_observation_context = None
        observation = getattr(request.state, "tenant_observation_context", None)
        with (
            metrics.bind_runtime(getattr(request.app.state, "metrics_runtime", None)),
            bound_tenant_observation(observation),
        ):
            return await call_next(request)

    @staticmethod
    def _unavailable_response() -> JSONResponse:
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Tenant policy is temporarily unavailable",
                type="service_unavailable",
                code="tenant_policy_unavailable",
            )
        )
        return JSONResponse(status_code=503, content=body.model_dump())
