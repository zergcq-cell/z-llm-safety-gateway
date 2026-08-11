"""Models listing endpoint — GET /v1/models.

Forwards a GET /models request to the first configured provider and passes
the response through to the client. Only the first provider is queried;
results are NOT aggregated across multiple providers.
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
    """Forward a GET /models request to the first configured provider.

    Only the first provider in the configuration is queried. The response
    body and status code are passed through to the client without modification.

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

    provider_config = config.providers[0]
    url = f"{provider_config.base_url}/models"

    # Build headers
    headers: dict[str, str] = {"Accept": "application/json"}
    if provider_config.api_key:
        headers["Authorization"] = f"Bearer {provider_config.api_key}"

    # Build query params (Azure api-version)
    params: dict[str, str] | None = None
    if provider_config.api_version:
        params = {"api-version": provider_config.api_version}

    timeout = float(config.security.timeout.get("upstream", 120))

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
