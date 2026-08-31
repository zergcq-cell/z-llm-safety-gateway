"""API key authentication middleware — Bearer token validation (fail-closed).

Validates the ``Authorization: Bearer <key>`` header against the configured
``security.auth.api_keys`` (key/name) list.  When authentication is enabled,
requests without a matching token are rejected with a 401 OpenAI-compatible
error body.  Matching requests are forwarded with ``request.state.api_key_name``
injected for downstream middleware and audit logging.

Auth defaults to disabled; enabling it explicitly turns on fail-closed
behaviour (requests without valid credentials are rejected).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from z_llm_safety_gateway.config.models import AuthConfig, TenancyConfig
from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.tenancy import LEGACY_TENANT_CONTEXT, TenantContext

logger = structlog.get_logger(__name__)

#: Prefix of the ``Authorization`` header scheme.
BEARER_PREFIX = "bearer "


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates Bearer API-key tokens.

    Args:
        config: The ``security.auth`` configuration.  When ``enabled`` is
            False (default), the middleware passes requests through without
            validating credentials.
    """

    def __init__(
        self,
        app: ASGIApp,
        config: AuthConfig,
        tenancy: TenancyConfig | None = None,
    ) -> None:
        super().__init__(app)
        self._enabled: bool = config.enabled
        tenancy_config = tenancy or TenancyConfig()
        raw_keys = [api_key.key for api_key in config.api_keys]
        if tenancy_config.enabled and len(raw_keys) != len(set(raw_keys)):
            raise ValueError("duplicate_api_key")
        # Map API key -> name for O(1) lookup without exposing key values.
        self._keys: dict[str, str] = {ak.key: ak.name for ak in config.api_keys}
        self._tenant_contexts: dict[str, TenantContext] = {}
        for api_key in config.api_keys:
            if tenancy_config.enabled:
                if api_key.tenant_id is None:
                    raise ValueError("api_key_tenant_required")
                context = TenantContext(
                    tenant_id=api_key.tenant_id,
                    identity_source="api_key",
                )
            else:
                context = LEGACY_TENANT_CONTEXT
            self._tenant_contexts[api_key.key] = context

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._enabled:
            request.state.tenant_context = LEGACY_TENANT_CONTEXT
            return await call_next(request)

        token = self._extract_token(request)
        api_key_name = self._keys.get(token) if token is not None else None
        tenant_context = (
            self._tenant_contexts.get(token) if token is not None else None
        )

        if api_key_name is None or tenant_context is None:
            logger.warning("auth_rejected", path=request.url.path)
            return self._unauthorized_response()

        request.state.api_key_name = api_key_name
        request.state.tenant_context = tenant_context
        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """Extract the Bearer token from the Authorization header, or None.

        The scheme is case-insensitive per RFC 7235.
        """
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith(BEARER_PREFIX):
            return None
        token = auth_header[len(BEARER_PREFIX) :].strip()
        return token or None

    @staticmethod
    def _unauthorized_response() -> JSONResponse:
        """Build a 401 OpenAI-compatible error response."""
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Invalid authentication credentials",
                type="invalid_request_error",
                code="invalid_api_key",
            )
        )
        return JSONResponse(status_code=401, content=body.model_dump())
