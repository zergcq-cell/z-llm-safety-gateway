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

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from z_llm_safety_gateway.audit.logger import AuditLogger, compute_content_hash
from z_llm_safety_gateway.audit.models import AuditEntry, DetectorAuditRecord
from z_llm_safety_gateway.config.models import _parse_duration
from z_llm_safety_gateway.content.extractor import extract_content
from z_llm_safety_gateway.content.writeback import apply_modifications
from z_llm_safety_gateway.exceptions import (
    OpenAIErrorBody,
    OpenAIErrorDetail,
    SafetyBlockError,
)
from z_llm_safety_gateway.language import detect_language, detect_language_for_messages
from z_llm_safety_gateway.models import DetectionContext, DetectionResult, find_result_by_action
from z_llm_safety_gateway.pipeline.engine import PipelineResult
from z_llm_safety_gateway.post_audit.audit import PostAuditRunner
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.router import ModelRouter
from z_llm_safety_gateway.recall.webhook import WebhookRecall
from z_llm_safety_gateway.streaming.handler import StreamingHandler, _extract_delta_text
from z_llm_safety_gateway.streaming.sse import (
    SSE_DONE,
    format_safety_block,
    format_safety_recall,
)

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
    return find_result_by_action(results, "block")


def _higher_risk(a: str | None, b: str | None) -> str | None:
    """Return the higher of two risk levels, or the non-None one."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _RISK_LEVEL_ORDER.get(a, 0) >= _RISK_LEVEL_ORDER.get(b, 0) else b


def _build_audit_entry(
    request_id: str,
    direction: Literal["input", "output"],
    model: str | None,
    provider_name: str | None,
    content: str,
    final_action: str,
    final_risk_level: str,
    detector_results: list[Any] | None = None,
    streaming: bool = False,
    language: str | None = None,
    pipeline_duration_ms: float = 0.0,
    total_duration_ms: float = 0.0,
    user_id: str | None = None,
    applied_modify: bool | None = None,
    **extra: Any,
) -> AuditEntry:
    """Build an AuditEntry from pipeline results.

    Args:
        request_id: The request trace ID.
        direction: "input" or "output".
        model: The model name from the request.
        provider_name: The provider name.
        content: The content that was detected.
        final_action: The final pipeline action.
        final_risk_level: The overall risk level.
        detector_results: List of DetectionResult objects.
        streaming: Whether this is a streaming response.
        language: Detected language code.
        pipeline_duration_ms: Pipeline execution time in ms.
        total_duration_ms: Total wall-clock duration (request entry to audit
            write) in ms — excludes provider latency for output entries.
        user_id: User ID extracted from the request body 'user' field.
        applied_modify: Whether a modify action was actually applied.
            True = modify applied (input/sync-output); False = modify
            downgraded to flag (streaming post-audit); None = not applicable.
        **extra: Additional AuditEntry fields (window_count, post_audit, etc.).
    """
    detectors: list[DetectorAuditRecord] = []
    for r in (detector_results or []):
        action = r.action
        applied: bool | None = None

        if r.action == "modify":
            if applied_modify is True:
                applied = True
            elif applied_modify is False:
                # Streaming post-audit: modify cannot be applied → downgrade.
                action = "flag"
                applied = False

        detectors.append(
            DetectorAuditRecord(
                name=r.detector_name,
                action=action,
                confidence=r.confidence,
                risk_level=r.risk_level,
                duration_ms=r.duration_ms,
                error=r.error,
                applied=applied,
            )
        )

    return AuditEntry(
        request_id=request_id,
        direction=direction,
        user_id=user_id,
        model=model,
        provider=provider_name,
        content_hash=compute_content_hash(content) if content else None,
        content_length=len(content),
        language=language,
        detectors=detectors,
        final_action=final_action,
        final_risk_level=final_risk_level,
        pipeline_duration_ms=pipeline_duration_ms,
        total_duration_ms=total_duration_ms,
        streaming=streaming,
        **extra,
    )


def _get_sync_timeout(request: Request) -> float:
    """Resolve the pipeline-level sync_timeout for output detection (B-08).

    Reads ``output_detection_config.sync_timeout`` (default '5s' per DESIGN 3.5).
    """
    output_detection_cfg = getattr(request.app.state, "output_detection_config", None)
    if output_detection_cfg is not None:
        return _parse_duration(output_detection_cfg.sync_timeout)
    return 5.0


def _handle_sync_timeout(
    output_detectors: list[Any],
    output_detector_configs: dict[str, dict[str, Any]],
) -> PipelineResult:
    """Create error results for all detectors when sync_timeout fires (B-08).

    Each detector is treated per its ``on_error`` strategy:
    - ``fail_open`` → action="allow" (skip the detector)
    - ``fail_closed`` → action="block"
    """
    error_results: list[DetectionResult] = []
    for det in output_detectors:
        det_name = det.name
        det_cfg = output_detector_configs.get(det_name, {})
        on_error: str = det_cfg.get("on_error", "fail_open")

        if on_error == "fail_closed":
            error_results.append(
                DetectionResult(
                    detector_name=det_name,
                    category="error",
                    action="block",
                    confidence=1.0,
                    risk_level="high",
                    message=(
                        f"Detector '{det_name}' timed out (fail_closed): "
                        "Pipeline sync_timeout exceeded"
                    ),
                    error="Pipeline sync_timeout exceeded",
                )
            )
        else:
            error_results.append(
                DetectionResult(
                    detector_name=det_name,
                    category="error",
                    action="allow",
                    confidence=0.0,
                    risk_level="low",
                    message=(
                        f"Detector '{det_name}' timed out (fail_open): "
                        "Pipeline sync_timeout exceeded"
                    ),
                    error="Pipeline sync_timeout exceeded",
                )
            )

    final_action = "block" if any(r.action == "block" for r in error_results) else "allow"
    risk_level = "high" if final_action == "block" else "low"

    return PipelineResult(
        final_action=final_action,
        overall_risk_level=risk_level,
        detector_results=error_results,
    )


def _build_streaming_response(
    request: Request,
    body: dict[str, Any],
    provider: Any,
    forward_headers: dict[str, str],
    request_id: str,
    model: str,
    engine: Any,
    audit_logger: AuditLogger | None,
    audit_enabled: bool,
    input_language: str | None = None,
    user_id: str | None = None,
) -> StreamingResponse:
    """Build a StreamingResponse for a ``stream=true`` chat completion request.

    Handles both ``sliding_window`` and ``buffer`` streaming modes, post-audit
    detection, recall signals, and audit logging.
    """
    streaming_config = getattr(request.app.state, "streaming_config", None)
    output_detectors: list[Any] = getattr(request.app.state, "output_detectors", [])
    output_detector_configs: dict[str, dict[str, Any]] = getattr(
        request.app.state, "output_detector_configs", {}
    )
    post_audit_runner: PostAuditRunner | None = getattr(
        request.app.state, "post_audit_runner", None
    )
    streaming_webhook: WebhookRecall | None = getattr(
        request.app.state, "streaming_webhook_recall", None
    )
    provider_name = provider.config.name

    headers: dict[str, str] = {"Cache-Control": "no-cache"}
    if request_id:
        headers["X-Request-ID"] = request_id
    headers["X-Safety-Action"] = getattr(request.state, "safety_action", "allow")

    has_detection = bool(output_detectors) and engine is not None
    is_buffer = (
        streaming_config is not None
        and streaming_config.mode == "buffer"
        and has_detection
    )

    async def _generate() -> AsyncIterator[str]:
        stream_start = time.monotonic()

        # --- No output detectors: transparent passthrough (backward compat) ---
        if not has_detection:
            try:
                async for chunk in provider.stream_forward(body, forward_headers):
                    yield chunk
            except ProviderError as exc:
                err = json.dumps(
                    {"error": {"message": exc.message, "type": "provider_error"}}
                )
                yield f"event: error\ndata: {err}\n\n"
            yield SSE_DONE
            return

        # --- Buffer mode (SC-010, SC-011) ---
        if is_buffer:
            buffered: list[str] = []
            full_content = ""
            try:
                async for chunk in provider.stream_forward(body, forward_headers):
                    buffered.append(chunk)
                    full_content += _extract_delta_text(chunk)
            except ProviderError as exc:
                err = json.dumps(
                    {"error": {"message": exc.message, "type": "provider_error"}}
                )
                yield f"event: error\ndata: {err}\n\n"
                yield SSE_DONE
                return

            context = DetectionContext(
                direction="output",
                request_id=request_id,
                metadata={"content": full_content},
            )
            result = await engine.run(
                output_detectors, [context], output_detector_configs
            )

            if result.final_action == "block":
                blk = find_result_by_action(result.detector_results, "block")
                yield format_safety_block(
                    request_id=request_id,
                    blocked_by=blk.detector_name if blk else "unknown",
                    category=blk.category if blk else "unknown",
                    risk_level=result.overall_risk_level,
                    confidence=blk.confidence if blk else 0.0,
                    reason=blk.message if blk else "Blocked by detector",
                )
                yield SSE_DONE
            else:
                for chunk in buffered:
                    yield chunk
                yield SSE_DONE

            # Buffer mode skips post-audit (full detection already done).
            if audit_enabled and audit_logger:
                audit_logger.record(
                    _build_audit_entry(
                        request_id=request_id,
                        direction="output",
                        model=model,
                        provider_name=provider_name,
                        content=full_content,
                        final_action=result.final_action,
                        final_risk_level=result.overall_risk_level,
                        detector_results=result.detector_results,
                        streaming=True,
                        pipeline_duration_ms=result.pipeline_duration_ms,
                        total_duration_ms=(time.monotonic() - stream_start) * 1000.0,
                        user_id=user_id,
                        post_audit={"executed": False},
                    )
                )
            return

        # --- Sliding window mode (SC-001 ~ SC-009) ---
        handler = StreamingHandler(
            engine=engine,
            output_detectors=output_detectors,
            detector_configs=output_detector_configs,
            window_size=streaming_config.window_size if streaming_config else 200,
            overlap=streaming_config.overlap if streaming_config else 50,
            send_flag_events=(
                streaming_config.send_flag_events if streaming_config else False
            ),
            request_id=request_id,
            max_response_size=(
                streaming_config.max_response_size if streaming_config else "1MB"
            ),
            on_max_size=streaming_config.on_max_size if streaming_config else "block",
            language=input_language,
        )

        try:
            async for chunk in provider.stream_forward(body, forward_headers):
                if handler.blocked:
                    break
                async for event in handler.process_chunk(chunk):
                    yield event
        except ProviderError as exc:
            err = json.dumps(
                {"error": {"message": exc.message, "type": "provider_error"}}
            )
            yield f"event: error\ndata: {err}\n\n"
            yield SSE_DONE
            if audit_enabled and audit_logger:
                audit_logger.record(
                    _build_audit_entry(
                        request_id=request_id,
                        direction="output",
                        model=model,
                        provider_name=provider_name,
                        content=handler.accumulated_content,
                        final_action=handler.output_action,
                        final_risk_level=handler.output_risk_level,
                        detector_results=handler.detector_results or None,
                        streaming=True,
                        window_count=handler.window_count,
                        language=input_language,
                        total_duration_ms=(time.monotonic() - stream_start) * 1000.0,
                        user_id=user_id,
                        post_audit={"executed": False},
                    )
                )
            return

        if not handler.blocked:
            # Flush residual SSE buffer content at stream end (B-03/SC-SSE-003).
            async for event in handler.drain():
                yield event
            handler.finish()
            yield SSE_DONE

        # --- Post-audit (SC-012, SC-013) ---
        post_audit_outcome: Any = None
        post_audit_info: dict[str, Any] | None = None
        recalled = False
        recall_method: str | None = None

        if (
            streaming_config
            and streaming_config.post_audit
            and output_detectors
            and post_audit_runner
        ):
            post_audit_outcome = await post_audit_runner.run(
                handler.accumulated_content,
                request_id=request_id,
                language=input_language,
            )
            post_audit_info = {
                "executed": True,
                "result": post_audit_outcome.effective_action,
                "category": post_audit_outcome.category or "",
                "risk_level": post_audit_outcome.risk_level,
            }

            if post_audit_outcome.recall_needed:
                recalled = True
                recall_method = streaming_config.recall.method
                if streaming_config.recall.method in ("sse", "both"):
                    yield format_safety_recall(
                        request_id=request_id,
                        risk_level=post_audit_outcome.risk_level,
                        reason=post_audit_outcome.reason or "",
                        category=post_audit_outcome.category or "",
                    )
                if (
                    streaming_config.recall.method in ("webhook", "both")
                    and streaming_webhook
                ):
                    await streaming_webhook.send(
                        request_id=request_id,
                        risk_level=post_audit_outcome.risk_level,
                        reason=post_audit_outcome.reason or "",
                        category=post_audit_outcome.category or "",
                    )

        # --- Audit logging for streaming ---
        # Use output-side results (B-05) and post-audit detector_results (B-06).
        if audit_enabled and audit_logger:
            audit_detector_results: list[Any] | None = None
            applied_modify: bool | None = None
            if post_audit_outcome is not None:
                audit_detector_results = post_audit_outcome.detector_results or None
                # Streaming post-audit: modify cannot be applied → downgrade.
                applied_modify = False
            else:
                audit_detector_results = handler.detector_results or None

            # When post-audit is skipped, post_audit should be {'executed': False}.
            effective_post_audit = post_audit_info or {"executed": False}

            audit_logger.record(
                _build_audit_entry(
                    request_id=request_id,
                    direction="output",
                    model=model,
                    provider_name=provider_name,
                    content=handler.accumulated_content,
                    final_action=handler.output_action,
                    final_risk_level=handler.output_risk_level,
                    detector_results=audit_detector_results,
                    streaming=True,
                    window_count=handler.window_count,
                    language=input_language,
                    total_duration_ms=(time.monotonic() - stream_start) * 1000.0,
                    user_id=user_id,
                    applied_modify=applied_modify,
                    post_audit=effective_post_audit,
                    recalled=recalled if recalled else None,
                    recall_method=recall_method,
                )
            )

    return StreamingResponse(
        content=_generate(),
        media_type="text/event-stream",
        headers=headers,
    )


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

    # Track total request duration from entry to audit write (B-09a).
    request_start = time.monotonic()
    # Extract user_id from request body 'user' field (B-09b).
    user_id_raw = body.get("user")
    user_id: str | None = str(user_id_raw) if user_id_raw else None

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

    input_pipeline_result: Any = None
    input_extracted: list[Any] | None = None
    input_language: str | None = None

    if input_detectors and engine:
        messages = body.get("messages", [])
        extracted = extract_content(messages)
        input_extracted = extracted

        if extracted:
            language = detect_language_for_messages(extracted)
            input_language = language
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
            input_pipeline_result = result

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

    # 5b. Input audit logging (SC-016)
    audit_cfg = getattr(request.app.state, "audit_config", None)
    audit_enabled = audit_cfg is not None and audit_cfg.enabled
    audit_logger: AuditLogger | None = getattr(
        request.app.state, "audit_logger", None
    )

    if audit_enabled and audit_logger:
        input_content = (
            " ".join(ec.text for ec in input_extracted) if input_extracted else ""
        )
        # Determine if input modify was applied (B-09e).
        input_applied_modify: bool | None = None
        if (
            input_pipeline_result is not None
            and input_pipeline_result.final_action == "modify"
            and input_pipeline_result.modifications
        ):
            input_applied_modify = True

        audit_logger.record(
            _build_audit_entry(
                request_id=request_id or "",
                direction="input",
                model=model,
                provider_name=provider.config.name,
                content=input_content,
                final_action=getattr(request.state, "safety_action", "allow"),
                final_risk_level=getattr(request.state, "safety_risk_level", "low")
                or "low",
                detector_results=(
                    input_pipeline_result.detector_results
                    if input_pipeline_result
                    else None
                ),
                language=input_language,
                pipeline_duration_ms=(
                    input_pipeline_result.pipeline_duration_ms
                    if input_pipeline_result
                    else 0.0
                ),
                total_duration_ms=(time.monotonic() - request_start) * 1000.0,
                user_id=user_id,
                applied_modify=input_applied_modify,
            )
        )

    # 6. Streaming branch (SC-001 ~ SC-013)
    if body.get("stream") is True:
        return _build_streaming_response(
            request,
            body,
            provider,
            forward_headers,
            request_id or "",
            model,
            engine,
            audit_logger,
            audit_enabled,
            input_language=input_language,
            user_id=user_id,
        )

    # 7. Forward request to provider (non-streaming)
    provider_response = await provider.forward_request(body, forward_headers)
    # Track output duration from provider response to response sent (B-09a).
    provider_response_time = time.monotonic()

    # 8. Output safety pipeline
    output_detectors: list[Any] = getattr(request.app.state, "output_detectors", [])
    output_detector_configs: dict[str, dict[str, Any]] = getattr(
        request.app.state, "output_detector_configs", {}
    )

    response_content = provider_response.content
    response_status = provider_response.status_code
    response_media_type = provider_response.headers.get(
        "content-type", "application/json"
    )

    # 8a. Async output detection (SC-014, SC-015)
    output_detection_cfg = getattr(request.app.state, "output_detection_config", None)
    if (
        output_detection_cfg
        and output_detection_cfg.mode == "async"
        and output_detectors
        and engine
    ):
        output_webhook: WebhookRecall | None = getattr(
            request.app.state, "output_webhook_recall", None
        )
        _req_id = request_id or ""
        _model = model
        _provider_name = provider.config.name
        _response_content = response_content
        _engine = engine
        _output_detectors = output_detectors
        _output_configs = output_detector_configs
        _audit_logger = audit_logger
        _audit_enabled = audit_enabled
        _user_id = user_id
        _provider_response_time = provider_response_time

        async def _async_output_detection() -> None:
            """Background output detection with webhook recall."""
            try:
                rj: dict[str, Any] = json.loads(_response_content)
                ch = rj.get("choices", [])
                if ch and isinstance(ch, list):
                    mo = ch[0].get("message", {}) if isinstance(ch[0], dict) else {}
                    otext = mo.get("content", "")
                    if otext and isinstance(otext, str):
                        olang = detect_language(otext)
                        octx = DetectionContext(
                            direction="output",
                            request_id=_req_id,
                            language=olang,
                            message_index=None,
                            metadata={"content": otext},
                        )
                        bg_result = await _engine.run(
                            _output_detectors, [octx], _output_configs
                        )

                        if (
                            bg_result.final_action in ("block", "modify")
                            and output_webhook
                        ):
                            blk = _find_block_result(bg_result.detector_results)
                            if blk:
                                await output_webhook.send(
                                    request_id=_req_id,
                                    risk_level=bg_result.overall_risk_level,
                                    reason=blk.message,
                                    category=blk.category,
                                )

                        if _audit_enabled and _audit_logger:
                            _audit_logger.record(
                                _build_audit_entry(
                                    request_id=_req_id,
                                    direction="output",
                                    model=_model,
                                    provider_name=_provider_name,
                                    content=otext,
                                    final_action=bg_result.final_action,
                                    final_risk_level=bg_result.overall_risk_level,
                                    detector_results=bg_result.detector_results,
                                    language=olang,
                                    pipeline_duration_ms=bg_result.pipeline_duration_ms,
                                    total_duration_ms=(
                                        time.monotonic() - _provider_response_time
                                    )
                                    * 1000.0,
                                    user_id=_user_id,
                                    async_detection="completed",
                                    recalled=bg_result.final_action == "block",
                                    recall_method=(
                                        "webhook"
                                        if bg_result.final_action == "block"
                                        else None
                                    ),
                                )
                            )
            except Exception:
                logger.warning("async_output_detection_failed", exc_info=True)

        asyncio.create_task(_async_output_detection())

        # Initial audit entry (pending)
        if audit_enabled and audit_logger:
            audit_logger.record(
                _build_audit_entry(
                    request_id=request_id or "",
                    direction="output",
                    model=model,
                    provider_name=provider.config.name,
                    content="",
                    final_action="allow",
                    final_risk_level="low",
                    total_duration_ms=(time.monotonic() - provider_response_time)
                    * 1000.0,
                    user_id=user_id,
                    async_detection="pending",
                )
            )

        return Response(
            content=response_content,
            status_code=response_status,
            media_type=response_media_type,
        )

    # 8b. Sync output detection (existing flow)
    output_pipeline_result: Any = None
    output_text_for_audit = ""

    if output_detectors and engine:
        try:
            response_json: dict[str, Any] = json.loads(provider_response.content)
            choices = response_json.get("choices", [])
            if choices and isinstance(choices, list):
                message_obj = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                output_text = message_obj.get("content", "")
                output_text_for_audit = output_text if isinstance(output_text, str) else ""

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

                    # B-08: wrap pipeline run in asyncio.wait_for(sync_timeout).
                    sync_timeout_seconds = _get_sync_timeout(request)
                    try:
                        result = await asyncio.wait_for(
                            engine.run(
                                output_detectors,
                                [output_context],
                                output_detector_configs,
                            ),
                            timeout=sync_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "sync_output_detection_timeout",
                            sync_timeout_seconds=sync_timeout_seconds,
                        )
                        result = _handle_sync_timeout(
                            output_detectors, output_detector_configs
                        )
                    output_pipeline_result = result

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
                        output_text_for_audit = modified_content
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            logger.warning(
                "output_pipeline_skipped",
                reason="invalid_response_format",
            )

    # 9. Output audit logging (sync mode, SC-016)
    if audit_enabled and audit_logger:
        # Determine if output modify was applied (B-09e).
        output_applied_modify: bool | None = None
        if (
            output_pipeline_result is not None
            and output_pipeline_result.final_action == "modify"
            and output_pipeline_result.modifications
        ):
            output_applied_modify = True

        audit_logger.record(
            _build_audit_entry(
                request_id=request_id or "",
                direction="output",
                model=model,
                provider_name=provider.config.name,
                content=output_text_for_audit,
                final_action=getattr(request.state, "safety_action", "allow"),
                final_risk_level=getattr(request.state, "safety_risk_level", "low")
                or "low",
                detector_results=(
                    output_pipeline_result.detector_results
                    if output_pipeline_result
                    else None
                ),
                pipeline_duration_ms=(
                    output_pipeline_result.pipeline_duration_ms
                    if output_pipeline_result
                    else 0.0
                ),
                total_duration_ms=(time.monotonic() - provider_response_time) * 1000.0,
                user_id=user_id,
                applied_modify=output_applied_modify,
            )
        )

    # 10. Return response (possibly modified)
    return Response(
        content=response_content,
        status_code=response_status,
        media_type=response_media_type,
    )
