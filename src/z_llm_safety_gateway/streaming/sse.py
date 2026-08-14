"""SSE event formatting for streaming (v0.3.0).

Implements DESIGN.md Section 4.3 SSE event types:
- ``data: {chunk}`` — standard OpenAI token events.
- ``event: safety_block`` + data payload — mid-stream block.
- ``event: safety_flag`` + data payload — per-window flag notification.
- ``data: [DONE]`` — stream completion.
"""

from __future__ import annotations

import json
from typing import Any

# Standard OpenAI stream termination marker.
SSE_DONE = "data: [DONE]\n\n"


def format_chunk(data: str) -> str:
    """Format a standard ``data:`` SSE event from *data*."""
    return f"data: {data}\n\n"


def _event(event_name: str, payload: dict[str, Any]) -> str:
    """Format a named SSE event with a JSON data payload."""
    body = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {body}\n\n"


def format_safety_block(
    request_id: str,
    blocked_by: str,
    category: str,
    risk_level: str,
    confidence: float,
    reason: str,
) -> str:
    """Format a ``safety_block`` SSE event."""
    return _event(
        "safety_block",
        {
            "request_id": request_id,
            "blocked_by": blocked_by,
            "category": category,
            "risk_level": risk_level,
            "confidence": confidence,
            "reason": reason,
        },
    )


def format_safety_flag(
    request_id: str,
    flagged_by: str,
    category: str,
    risk_level: str,
    confidence: float,
    message: str,
) -> str:
    """Format a ``safety_flag`` SSE event.

    ``flagged_by`` is a comma-separated list of flagging detectors aggregated
    into a single event (DESIGN.md Section 8.2 event granularity).
    """
    return _event(
        "safety_flag",
        {
            "request_id": request_id,
            "flagged_by": flagged_by,
            "category": category,
            "risk_level": risk_level,
            "confidence": confidence,
            "message": message,
        },
    )


def format_safety_recall(
    request_id: str,
    risk_level: str,
    reason: str,
    category: str,
) -> str:
    """Format a ``safety_recall`` SSE event for post-audit recall."""
    return _event(
        "safety_recall",
        {
            "request_id": request_id,
            "risk_level": risk_level,
            "reason": reason,
            "category": category,
        },
    )


# SSE event boundary delimiter (blank line terminates an event).
_SSE_BOUNDARY = "\n\n"


class SSEBuffer:
    """Buffers raw SSE text chunks and yields complete events.

    SSE events are delimited by ``\\n\\n`` (a blank line).  When a provider
    streams via ``aiter_text()``, a single ``data: {json}\\n\\n`` event may be
    split across two adjacent chunks.  This buffer accumulates raw text and
    only yields events once the ``\\n\\n`` boundary is seen, ensuring no
    partial events are passed downstream (B-03 / Decision 14).
    """

    def __init__(self) -> None:
        self._buffer: str = ""

    def feed(self, chunk: str) -> list[str]:
        """Feed a raw text *chunk* and return all complete SSE events.

        Complete events are those terminated by ``\\n\\n``.  The returned
        strings include the trailing ``\\n\\n`` delimiter so they can be
        forwarded to the client as-is.
        """
        self._buffer += chunk
        events: list[str] = []
        while _SSE_BOUNDARY in self._buffer:
            idx = self._buffer.index(_SSE_BOUNDARY)
            # Include the delimiter in the event text.
            event = self._buffer[: idx + len(_SSE_BOUNDARY)]
            self._buffer = self._buffer[idx + len(_SSE_BOUNDARY) :]
            events.append(event)
        return events

    def flush(self) -> str | None:
        """Return residual buffer content (if any) and clear the buffer.

        Called at stream end to ensure trailing content without a ``\\n\\n``
        terminator is not silently dropped.  Returns ``None`` when the buffer
        is empty.
        """
        if self._buffer:
            residual = self._buffer
            self._buffer = ""
            return residual
        return None

    @property
    def pending(self) -> str:
        """Return the current pending (incomplete) buffer content."""
        return self._buffer
