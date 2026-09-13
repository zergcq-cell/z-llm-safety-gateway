"""Per-tenant bounded request resource middleware."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from time import monotonic
from typing import Any, cast

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from z_llm_safety_gateway.tenancy.failures import FailureKind, FailureOutcome
from z_llm_safety_gateway.tenancy.resources import (
    TenantResourceExhausted,
    TenantResourceManager,
    TenantResourceTimeout,
)


class TenantResourceMiddleware(BaseHTTPMiddleware):
    """Acquire and release a tenant lease around the complete request."""

    def __init__(self, app: ASGIApp, manager: TenantResourceManager) -> None:
        super().__init__(app)
        self._manager = manager

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        context = getattr(request.state, "tenant_context", None)
        tenant_id = getattr(context, "tenant_id", "default")
        snapshot = await self._manager.snapshot(tenant_id)
        request.state.resource_snapshot = snapshot
        request.state.tenant_resource_manager = self._manager
        try:
            lease = await self._manager.acquire(snapshot)
        except (TenantResourceExhausted, TenantResourceTimeout) as exc:
            kind = (
                FailureKind.CAPACITY_EXHAUSTED
                if isinstance(exc, TenantResourceExhausted)
                else FailureKind.TIMEOUT
            )
            outcome = FailureOutcome.from_kind(kind)
            return JSONResponse(
                status_code=outcome.http_status(), content=outcome.public_body()
            )
        try:
            response = await asyncio.wait_for(
                call_next(request), max(0.001, snapshot.deadline - monotonic())
            )
            body_iterator = getattr(response, "body_iterator", None)
            if body_iterator is not None and hasattr(body_iterator, "__aiter__"):
                async def _bounded_stream() -> AsyncIterator[bytes]:
                    try:
                        async for chunk in body_iterator:
                            yield chunk
                    finally:
                        await lease.release()
                cast(Any, response).body_iterator = _bounded_stream()
                return response
            await lease.release()
            return response
        except BaseException:
            await lease.release()
            raise
