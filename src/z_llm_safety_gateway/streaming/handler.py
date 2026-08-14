"""Streaming handler — per-chunk sliding-window detection (v0.3.0).

Processes provider SSE chunks and applies sliding-window safety detection,
emitting events to the client.  Implements DESIGN.md Section 8.2 action table:

- ``block``: stop forwarding, emit ``safety_block`` + ``[DONE]``.
- ``flag``: continue; emit ``safety_flag`` if ``send_flag_events`` is enabled.
- ``modify``: downgraded to ``flag`` (tokens already forwarded).
- ``allow``: continue forwarding.

v0.4.0 fixes (B-03/B-05/B-06/B-07):

- Uses :class:`SSEBuffer` to reassemble SSE events split across chunks (B-03).
- Maintains output-side ``output_action`` / ``output_risk_level`` independently
  of input-side state (B-05).
- Tracks ``window_count`` and collects ``detector_results`` for audit (B-06).
- Accepts and propagates ``language`` from the input side (B-07).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from z_llm_safety_gateway.models import DetectionContext, DetectionResult, find_result_by_action
from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult
from z_llm_safety_gateway.streaming.memory import StreamingMemory
from z_llm_safety_gateway.streaming.sliding_window import SlidingWindow
from z_llm_safety_gateway.streaming.sse import (
    SSE_DONE,
    SSEBuffer,
    format_safety_block,
    format_safety_flag,
)

# Action precedence for aggregating output-side results (higher = more severe).
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


def _higher_risk(a: str, b: str) -> str:
    """Return the higher of two risk levels."""
    return a if _RISK_LEVEL_ORDER.get(a, 0) >= _RISK_LEVEL_ORDER.get(b, 0) else b


def _extract_delta_text(chunk: str) -> str:
    """Extract the text content from an OpenAI SSE chunk (best-effort).

    Parses ``data: {json}`` chunks and returns the ``choices[0].delta.content``
    string.  Returns an empty string for non-content chunks (e.g. ``[DONE]``)
    or malformed chunks (which are forwarded transparently).
    """
    if not chunk.startswith("data:"):
        return ""
    payload = chunk[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return ""
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return ""
    try:
        delta = obj["choices"][0]["delta"]
        content = delta.get("content", "")
        return content if isinstance(content, str) else ""
    except (KeyError, IndexError, TypeError):
        return ""


class StreamingHandler:
    """Drives sliding-window detection over an SSE streaming response.

    Args:
        engine: The PipelineEngine used for window detection.
        output_detectors: List of initialized output Detector instances.
        detector_configs: Detector name → config dict mapping.
        window_size: Character window size (default 200).
        overlap: Character overlap between windows (default 50).
        send_flag_events: Whether to emit ``safety_flag`` SSE events.
        request_id: The current request id (for safety events).
        max_response_size: Byte-based accumulation limit.
        on_max_size: ``block`` or ``truncate`` policy.
        language: Input-side language code to reuse for output detection.
    """

    def __init__(
        self,
        engine: PipelineEngine,
        output_detectors: list[Any],
        detector_configs: dict[str, dict[str, Any]],
        window_size: int = 200,
        overlap: int = 50,
        send_flag_events: bool = False,
        request_id: str = "",
        max_response_size: str = "1MB",
        on_max_size: str = "block",
        language: str | None = None,
    ) -> None:
        self._engine = engine
        self._detectors = output_detectors
        self._configs = detector_configs
        self._window = SlidingWindow(window_size=window_size, overlap=overlap)
        self._send_flag_events = send_flag_events
        self._request_id = request_id
        self._language = language
        self._memory = StreamingMemory(
            max_response_size=max_response_size, on_max_size=on_max_size
        )
        self._sse_buffer = SSEBuffer()
        self._blocked = False
        self._accumulated = ""
        self.completed = False
        # Output-side state (B-05/B-06).
        self._output_action: str = "allow"
        self._output_risk_level: str = "low"
        self._window_count: int = 0
        self._detector_results: list[DetectionResult] = []

    @property
    def blocked(self) -> bool:
        """Return True if the stream was blocked mid-stream."""
        return self._blocked

    @property
    def accumulated_content(self) -> str:
        """Return the full accumulated response content."""
        return self._accumulated

    @property
    def window_count(self) -> int:
        """Return the number of detection windows actually processed."""
        return self._window_count

    @property
    def output_action(self) -> str:
        """Return the aggregated output-side action (B-05)."""
        return self._output_action

    @property
    def output_risk_level(self) -> str:
        """Return the highest output-side risk level across all windows."""
        return self._output_risk_level

    @property
    def language(self) -> str | None:
        """Return the input-side language reused for output detection (B-07)."""
        return self._language

    @property
    def detector_results(self) -> list[DetectionResult]:
        """Return detector results collected from sliding-window detection."""
        return self._detector_results

    async def process_chunk(self, chunk: str) -> AsyncIterator[str]:
        """Process a single provider chunk and yield client events.

        The raw chunk is fed to :class:`SSEBuffer` which reassembles complete
        SSE events (split by ``\\n\\n``).  Each complete event is forwarded to
        the client and its delta text is extracted for sliding-window
        detection.
        """
        if self._blocked:
            return

        for event in self._sse_buffer.feed(chunk):
            async for out in self._process_event(event):
                yield out
            if self._blocked:
                return

    async def drain(self) -> AsyncIterator[str]:
        """Flush residual SSE buffer content at stream end (SC-SSE-003).

        Called after the provider stream finishes to ensure trailing content
        without a ``\\n\\n`` terminator is not silently dropped.
        """
        if self._blocked:
            return

        residual = self._sse_buffer.flush()
        if residual:
            async for out in self._process_event(residual):
                yield out

    async def _process_event(self, event: str) -> AsyncIterator[str]:
        """Process one complete (or residual) SSE event.

        Forwards the event to the client, extracts delta text, and runs
        sliding-window detection on each ready window.
        """
        # Forward the event transparently (preserving order).
        if not self._blocked:
            yield event

        text = _extract_delta_text(event)
        if not text or self._blocked:
            return

        self._accumulated += text
        self._window.append(text)

        # Enforce max_response_size.
        if self._memory.check_exceeded(self._accumulated):
            if self._memory.policy == "block":
                self._blocked = True
                self._output_action = "block"
                self._output_risk_level = _higher_risk(
                    self._output_risk_level, "medium"
                )
                yield format_safety_block(
                    request_id=self._request_id,
                    blocked_by="streaming_limit",
                    category="response_too_long",
                    risk_level="medium",
                    confidence=1.0,
                    reason=f"Response exceeded max_response_size ({self._memory.policy})",
                )
                yield SSE_DONE
                return
            # truncate: stop accumulating but continue streaming
            self._accumulated = self._accumulated[:0]

        # Detect on each ready window.
        while self._window.is_ready() and not self._blocked:
            content, _retained = self._window.consume_window()
            self._window_count += 1
            result: PipelineResult = await self._engine.run(
                self._detectors, [self._make_context(content)], self._configs
            )

            # Update output-side state (B-05).
            self._update_output_state(result)
            # Collect detector results for audit (B-06).
            self._detector_results.extend(result.detector_results)

            if result.final_action == "block":
                self._blocked = True
                block = find_result_by_action(result.detector_results, "block")
                yield format_safety_block(
                    request_id=self._request_id,
                    blocked_by=block.detector_name if block else "unknown",
                    category=block.category if block else "unknown",
                    risk_level=result.overall_risk_level,
                    confidence=block.confidence if block else 0.0,
                    reason=block.message if block else "Blocked by detector",
                )
                yield SSE_DONE
                return
            elif result.final_action in ("flag", "modify"):
                # modify is downgraded to flag in streaming.
                if self._send_flag_events:
                    flagged_by = ",".join(
                        r.detector_name for r in result.detector_results
                    ) or "unknown"
                    first = find_result_by_action(result.detector_results, {"flag", "modify"})
                    yield format_safety_flag(
                        request_id=self._request_id,
                        flagged_by=flagged_by,
                        category=first.category if first else "unknown",
                        risk_level=result.overall_risk_level,
                        confidence=first.confidence if first else 0.0,
                        message="Streaming window flagged",
                    )
                # continue streaming
            # allow: continue

    def _update_output_state(self, result: PipelineResult) -> None:
        """Aggregate output-side action and risk level from a window result."""
        if _ACTION_PRECEDENCE.get(result.final_action, 0) > _ACTION_PRECEDENCE.get(
            self._output_action, 0
        ):
            self._output_action = result.final_action
        self._output_risk_level = _higher_risk(
            self._output_risk_level, result.overall_risk_level
        )

    def _make_context(self, content: str) -> DetectionContext:
        """Build a DetectionContext for window detection (direction output)."""
        return DetectionContext(
            direction="output",
            request_id=self._request_id,
            language=self._language,
            metadata={"content": content},
        )

    def finish(self) -> None:
        """Mark the stream as completed (invoked after [DONE] is sent)."""
        self.completed = True
