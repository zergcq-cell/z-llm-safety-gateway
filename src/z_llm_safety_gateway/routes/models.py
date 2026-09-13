"""Models listing endpoint — GET /v1/models.

Forwards GET /models to the tenant policy's explicit models Provider, or to
the first configured Provider on the legacy single-tenant path. Results are
never aggregated across Providers.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from z_llm_safety_gateway.config.models import GatewayConfig
from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.providers.base import ProviderError

router = APIRouter(tags=["models"])


@router.get("/v1/models")
async def list_models(request: Request) -> Response:
    """Forward GET /models through the request's resolved Provider domain.

    Tenant mode uses its explicit models Provider; legacy mode uses the first
    configured Provider. The upstream response is passed through unchanged.

    Raises:
        ProviderError: If the provider returns an HTTP error or a network
            error occurs (caught by the global exception handler).
    """
    config: GatewayConfig = request.app.state.config

    if not config.providers:
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="No providers configured",
                type="internal_error",
                code="no_providers",
            )
        )
        return JSONResponse(status_code=500, content=body.model_dump())

    tenant_bundle = getattr(request.state, "_tenant_runtime_bundle", None)
    if tenant_bundle is not None and tenant_bundle.router_view is None:
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Tenant policy is temporarily unavailable",
                type="service_unavailable",
                code="tenant_policy_unavailable",
            )
        )
        return JSONResponse(status_code=503, content=body.model_dump())
    if tenant_bundle is not None:
        provider = tenant_bundle.router_view.models_provider
    else:
        provider = request.app.state.router.models_provider()
    provider_config = provider.config
    url = f"{provider_config.base_url.rstrip('/')}/models"
    if provider_config.type == "anthropic":
        url = f"{provider_config.base_url.rstrip('/')}/models"

    # Build headers
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider_config.type == "anthropic" and provider_config.api_key:
        headers["x-api-key"] = provider_config.api_key
        if provider_config.api_version:
            headers["anthropic-version"] = provider_config.api_version
    elif provider_config.type == "gemini" and provider_config.api_key:
        headers["x-goog-api-key"] = provider_config.api_key
    elif provider_config.api_key:
        headers["Authorization"] = f"Bearer {provider_config.api_key}"

    # Build query params (Azure api-version)
    params: dict[str, str] | None = None
    if provider_config.api_version:
        params = {"api-version": provider_config.api_version}

    timeout = config.security.timeout.upstream_seconds

    # Make GET request to the provider
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params)
    except httpx.TimeoutException:
        raise ProviderError(
            provider_name=provider_config.name,
            message=f"Provider '{provider_config.name}' timeout after {timeout}s",
        ) from None
    except httpx.HTTPError:
        raise ProviderError(
            provider_name=provider_config.name,
            message=f"Network error connecting to provider '{provider_config.name}'",
        ) from None

    # Check for HTTP errors
    if response.status_code >= 400:
        raise ProviderError(
            provider_name=provider_config.name,
            message=f"Provider '{provider_config.name}' returned HTTP {response.status_code}",
            status_code=response.status_code,
        )

    # Return provider response (passthrough body and status code)
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type", "application/json"),
    )
