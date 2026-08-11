"""Chat completions endpoint — POST /v1/chat/completions.

Forwards chat completion requests to the appropriate LLM provider via the
ModelRouter. The provider response (body and status code) is passed through
to the client transparently.

Error handling:
- Invalid JSON body → 400 invalid_request_error
- Missing "model" field → 400 invalid_request_error
- No matching routing rule → 404 model_not_found (via ProviderError handler)
- Provider HTTP error → 502 provider_error (via ProviderError handler)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.providers.router import ModelRouter

router = APIRouter(tags=["chat"])


def _error_response(
    status_code: int,
    message: str,
    error_type: str = "invalid_request_error",
    code: str | None = None,
) -> JSONResponse:
    """Build an OpenAI-compatible JSON error response."""
    body = OpenAIErrorBody(
        error=OpenAIErrorDetail(
            message=message,
            type=error_type,
            code=code,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Forward a chat completion request to the routed provider.

    Steps:
        1. Parse the JSON request body.
        2. Extract the "model" field for routing.
        3. Route to the matching provider via ModelRouter.
        4. Forward the request body to the provider.
        5. Return the provider response (body and status code passthrough).

    Raises:
        ProviderError: If the provider returns an error or no routing rule
            matches (caught by the global exception handler).
    """
    # 1. Parse JSON body
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return _error_response(
            status_code=400,
            message="Invalid JSON in request body",
            error_type="invalid_request_error",
            code="invalid_json",
        )

    # 2. Extract model field
    model = body.get("model")
    if not model or not isinstance(model, str):
        return _error_response(
            status_code=400,
            message="Missing or invalid required field: model",
            error_type="invalid_request_error",
            code="missing_model",
        )

    # 3. Route to provider
    model_router: ModelRouter = request.app.state.router
    provider = model_router.route(model)

    # 4. Build forward headers (X-Request-ID for tracing)
    forward_headers: dict[str, str] = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        forward_headers["X-Request-ID"] = request_id

    # 5. Forward request to provider
    provider_response = await provider.forward_request(body, forward_headers)

    # 6. Return provider response (passthrough body and status code)
    return Response(
        content=provider_response.content,
        status_code=provider_response.status_code,
        media_type=provider_response.headers.get("content-type", "application/json"),
    )
