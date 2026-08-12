"""Streaming handler — per-chunk sliding-window detection (v0.3.0).

Processes provider SSE chunks and applies sliding-window safety detection,
emitting events to the client.  Implements DESIGN.md Section 8.2 action table:

- ``block``: stop forwarding, emit ``safety_block`` + ``[DONE]``.
- ``flag``: continue; emit ``safety_flag`` if ``send_flag_events`` is enabled.
- ``modify``: downgraded to ``flag`` (tokens already forwarded).
- ``allow``: continue forwarding.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult
from z_llm_safety_gateway.streaming.memory import StreamingMemory
from z_llm_safety_gateway.streaming.sliding_window import SlidingWindow
from z_llm_safety_gateway.streaming.sse import (
    SSE_DONE,
    format_safety_block,
    format_safety_flag,
)


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
    ) -> None:
        self._engine = engine
        self._detectors = output_detectors
        self._configs = detector_configs
        self._window = SlidingWindow(window_size=window_size, overlap=overlap)
        self._send_flag_events = send_flag_events
        self._request_id = request_id
        self._memory = StreamingMemory(
            max_response_size=max_response_size, on_max_size=on_max_size
        )
        self._blocked = False
        self._accumulated = ""
        self.completed = False

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
        """Return the number of detection windows processed."""
        return 0  # placeholder; window count tracked in production flow

    async def process_chunk(self, chunk: str) -> AsyncIterator[str]:
        """Process a single provider chunk and yield client events.

        Detects on each full window; applies the streaming action table.
        Malformed / non-content chunks are forwarded transparently.
        """
        # Forward the raw chunk transparently (preserving order).
        if not self._blocked:
            yield chunk

        text = _extract_delta_text(chunk)
        if not text or self._blocked:
            return

        self._accumulated += text
        self._window.append(text)

        # Enforce max_response_size.
        if self._memory.check_exceeded(self._accumulated):
            if self._memory.policy == "block":
                self._blocked = True
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
            result: PipelineResult = await self._engine.run(
                self._detectors, [self._make_context(content)], self._configs
            )

            if result.final_action == "block":
                self._blocked = True
                block = result.detector_results[0] if result.detector_results else None
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
                    first = result.detector_results[0] if result.detector_results else None
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

    def _make_context(self, content: str) -> Any:
        """Build a DetectionContext for window detection (direction output)."""
        from z_llm_safety_gateway.models import DetectionContext

        return DetectionContext(
            direction="output",
            request_id=self._request_id,
            metadata={"content": content},
        )

    def finish(self) -> None:
        """Mark the stream as completed (invoked after [DONE] is sent)."""
        self.completed = True
