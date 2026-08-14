"""Token-bucket rate limiting middleware — 429 + Retry-After.

Limits requests per ``api_key`` or per client ``ip`` using an in-memory token
bucket (:class:`~z_llm_safety_gateway.ratelimit.token_bucket.TokenBucket`).
When a bucket is exhausted the middleware rejects the request with a 429
OpenAI-compatible error body and a ``Retry-After`` header indicating the
suggested retry delay in seconds.

Bucket dimension is controlled by ``security.rate_limit.per``:
- ``api_key``: keyed on ``request.state.api_key_name`` (set by AuthMiddleware).
- ``ip``: keyed on the client IP address.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from z_llm_safety_gateway.config.models import RateLimitConfig
from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.ratelimit.token_bucket import TokenBucket

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces a token-bucket rate limit per key or IP.

    Args:
        config: The ``security.rate_limit`` configuration (rate/burst/per).
    """

    def __init__(self, app: ASGIApp, config: RateLimitConfig) -> None:
        super().__init__(app)
        self._enabled: bool = config.enabled
        self._rate: float = float(config.rate)
        self._burst: int = config.burst
        self._per: str = config.per
        self._buckets: dict[str, TokenBucket] = {}
        self._buckets_lock: asyncio.Lock = asyncio.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._enabled:
            return await call_next(request)

        identifier = self._identifier(request)
        bucket = await self._get_bucket(identifier)

        if not await bucket.consume():
            retry_after = max(1, math.ceil(bucket.retry_after()))
            logger.warning(
                "rate_limit_rejected",
                key=identifier,
                retry_after=retry_after,
            )
            return self._too_many_response(retry_after)

        return await call_next(request)

    def _identifier(self, request: Request) -> str:
        """Compute the bucket identifier for the current request."""
        client_host = request.client.host if request.client else "unknown"
        if self._per == "ip":
            return f"ip:{client_host}"
        api_key_name = getattr(request.state, "api_key_name", None)
        if api_key_name:
            return f"api_key:{api_key_name}"
        # Auth disabled or no key set: fall back to the client IP.
        return f"ip:{client_host}"

    async def _get_bucket(self, key: str) -> TokenBucket:
        """Return the bucket for *key*, creating it if necessary."""
        async with self._buckets_lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(rate=self._rate, burst=self._burst)
                self._buckets[key] = bucket
            return bucket

    @staticmethod
    def _too_many_response(retry_after: int) -> JSONResponse:
        """Build a 429 OpenAI-compatible error response with Retry-After."""
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="You have exceeded your rate limit",
                type="rate_limit_error",
                code="rate_limit_exceeded",
            )
        )
        response = JSONResponse(status_code=429, content=body.model_dump())
        response.headers["Retry-After"] = str(retry_after)
        return response
