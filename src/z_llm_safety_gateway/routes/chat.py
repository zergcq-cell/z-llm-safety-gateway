"""Chat completions endpoint — POST /v1/chat/completions.

Forwards chat completion requests to the appropriate LLM provider via the
ModelRouter, integrating the safety pipeline (input and output detection)
with the FastAPI request/response flow.

Pipeline integration:
- **Input pipeline**: extracts content from request messages, runs configured
  input detectors before forwarding to the provider. May block, modify, or
  flag the request.
- **Output pipeline**: extracts content from the provider response, runs
  configured output detectors after the provider responds. May block, modify,
  or flag the response.

When no detectors are configured, the endpoint behaves as a transparent
passthrough (backward compatible with v0.1.0).

Error handling:
- Invalid JSON body -> 400 invalid_request_error
- Missing "model" field -> 400 invalid_request_error
- No matching routing rule -> 404 model_not_found (via ProviderError handler)
- Provider HTTP error -> 502 provider_error (via ProviderError handler)
- Safety block (input) -> 400 safety_input_blocked (via SafetyBlockError handler)
- Safety block (output) -> 422 safety_output_blocked (via SafetyBlockError handler)
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from z_llm_safety_gateway.content.extractor import extract_content
from z_llm_safety_gateway.content.writeback import apply_modifications
from z_llm_safety_gateway.exceptions import (
    OpenAIErrorBody,
    OpenAIErrorDetail,
    SafetyBlockError,
)
from z_llm_safety_gateway.language import detect_language, detect_language_for_messages
from z_llm_safety_gateway.models import DetectionContext
from z_llm_safety_gateway.providers.router import ModelRouter

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])

# Action precedence for comparing input/output results (higher = more severe).
_ACTION_PRECEDENCE: dict[str, int] = {
    "allow": 0,
    "flag": 1,
    "modify": 2,
    "block": 3,
}

# Risk-level ordering (higher = more severe).
_RISK_LEVEL_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


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


def _find_block_result(results: list[Any]) -> Any | None:
    """Find the first DetectionResult with action == 'block'."""
    for r in results:
        if r.action == "block":
            return r
    return None


def _higher_risk(a: str | None, b: str | None) -> str | None:
    """Return the higher of two risk levels, or the non-None one."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _RISK_LEVEL_ORDER.get(a, 0) >= _RISK_LEVEL_ORDER.get(b, 0) else b


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Forward a chat completion request to the routed provider with safety pipeline.

    Steps:
        1. Parse the JSON request body.
        2. Extract the "model" field for routing.
        3. Route to the matching provider via ModelRouter.
        4. Run the input safety pipeline (if detectors are configured).
        5. Forward the (possibly modified) request body to the provider.
        6. Run the output safety pipeline on the provider response.
        7. Return the (possibly modified) response.

    Raises:
        ProviderError: If the provider returns an error or no routing rule
            matches (caught by the global exception handler).
        SafetyBlockError: If the input or output pipeline blocks the request
            (caught by the global exception handler).
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

    # 5. Input safety pipeline
    input_detectors: list[Any] = getattr(request.app.state, "input_detectors", [])
    input_detector_configs: dict[str, dict[str, Any]] = getattr(
        request.app.state, "input_detector_configs", {}
    )
    engine = getattr(request.app.state, "pipeline_engine", None)

    if input_detectors and engine:
        messages = body.get("messages", [])
        extracted = extract_content(messages)

        if extracted:
            language = detect_language_for_messages(extracted)
            request_id_val = getattr(request.state, "request_id", "")

            contexts = [
                DetectionContext(
                    direction="input",
                    request_id=request_id_val,
                    language=language,
                    message_index=ec.message_index,
                    metadata={"content": ec.text, "role": ec.role},
                )
                for ec in extracted
            ]

            result = await engine.run(input_detectors, contexts, input_detector_configs)

            # Store result in request.state for middleware
            request.state.safety_action = result.final_action
            request.state.safety_risk_level = result.overall_risk_level

            logger.info(
                "input_pipeline_complete",
                final_action=result.final_action,
                risk_level=result.overall_risk_level,
                detector_count=len(result.detector_results),
            )

            if result.final_action == "block":
                block_result = _find_block_result(result.detector_results)
                if block_result:
                    raise SafetyBlockError(
                        detector_name=block_result.detector_name,
                        category=block_result.category,
                        risk_level=block_result.risk_level,
                        confidence=block_result.confidence,
                        message=block_result.message,
                        direction="input",
                    )

            if result.final_action == "modify" and result.modifications:
                body = apply_modifications(body, result.modifications)
        else:
            request.state.safety_action = "allow"
    else:
        # No input detectors configured — passthrough
        request.state.safety_action = "allow"

    # 6. Forward request to provider
    provider_response = await provider.forward_request(body, forward_headers)

    # 7. Output safety pipeline
    output_detectors: list[Any] = getattr(request.app.state, "output_detectors", [])
    output_detector_configs: dict[str, dict[str, Any]] = getattr(
        request.app.state, "output_detector_configs", {}
    )

    response_content = provider_response.content
    response_status = provider_response.status_code
    response_media_type = provider_response.headers.get("content-type", "application/json")

    if output_detectors and engine:
        try:
            response_json: dict[str, Any] = json.loads(provider_response.content)
            choices = response_json.get("choices", [])
            if choices and isinstance(choices, list):
                message_obj = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                output_text = message_obj.get("content", "")

                if output_text and isinstance(output_text, str):
                    language = detect_language(output_text)
                    request_id_val = getattr(request.state, "request_id", "")

                    output_context = DetectionContext(
                        direction="output",
                        request_id=request_id_val,
                        language=language,
                        message_index=None,
                        metadata={"content": output_text},
                    )

                    result = await engine.run(
                        output_detectors, [output_context], output_detector_configs
                    )

                    # Update request.state — keep highest of input/output
                    current_action = getattr(request.state, "safety_action", "allow")
                    current_risk = getattr(request.state, "safety_risk_level", None)

                    if _ACTION_PRECEDENCE.get(result.final_action, 0) > _ACTION_PRECEDENCE.get(
                        current_action, 0
                    ):
                        request.state.safety_action = result.final_action

                    request.state.safety_risk_level = _higher_risk(
                        current_risk, result.overall_risk_level
                    )

                    logger.info(
                        "output_pipeline_complete",
                        final_action=result.final_action,
                        risk_level=result.overall_risk_level,
                        detector_count=len(result.detector_results),
                    )

                    if result.final_action == "block":
                        block_result = _find_block_result(result.detector_results)
                        if block_result:
                            raise SafetyBlockError(
                                detector_name=block_result.detector_name,
                                category=block_result.category,
                                risk_level=block_result.risk_level,
                                confidence=block_result.confidence,
                                message=block_result.message,
                                direction="output",
                            )

                    if result.final_action == "modify" and result.modifications:
                        # Write modified content back to response
                        modified_content = result.modifications[0].modified_content
                        message_obj["content"] = modified_content
                        response_content = json.dumps(response_json).encode()
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            logger.warning(
                "output_pipeline_skipped",
                reason="invalid_response_format",
            )

    # 8. Return response (possibly modified)
    return Response(
        content=response_content,
        status_code=response_status,
        media_type=response_media_type,
    )
