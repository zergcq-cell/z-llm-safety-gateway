"""Unit tests for SSEBuffer — cross-chunk SSE event reassembly.

Covers TC-SSE-001 ~ TC-SSE-005 (sse-streaming spec, B-03 / Decision 14).
"""

from __future__ import annotations

import json

from z_llm_safety_gateway.streaming.handler import _extract_delta_text
from z_llm_safety_gateway.streaming.sse import SSEBuffer


def _sse_data_event(payload: dict) -> str:
    """Build a complete ``data: {json}\\n\\n`` SSE event."""
    return f"data: {json.dumps(payload)}\n\n"


# --------------------------------------------------------------------------- #
# TC-SSE-001: Split event across two chunks is reassembled
# --------------------------------------------------------------------------- #
async def test_sse_buffer_reassembles_split_event():
    """TC-SSE-001: a single ``data:{json}\\n\\n`` split across two chunks is
    reassembled into one complete event with no byte loss or duplication."""
    original = _sse_data_event({"choices": [{"delta": {"content": "hello"}}]})
    mid = len(original) // 2
    part_a = original[:mid]
    part_b = original[mid:]

    buf = SSEBuffer()
    events_a = buf.feed(part_a)
    assert events_a == []  # incomplete — nothing yielded yet

    events_b = buf.feed(part_b)
    assert len(events_b) == 1
    assert events_b[0] == original  # exact reconstruction


# --------------------------------------------------------------------------- #
# TC-SSE-002: Multiple events in a single chunk are split by \n\n
# --------------------------------------------------------------------------- #
async def test_sse_buffer_splits_multiple_events_in_one_chunk():
    """TC-SSE-002: a chunk containing multiple ``\\n\\n``-delimited events
    yields all events in original order, strictly split on ``\\n\\n``."""
    ev1 = _sse_data_event({"choices": [{"delta": {"content": "foo"}}]})
    ev2 = _sse_data_event({"choices": [{"delta": {"content": "bar"}}]})
    ev3 = "data: [DONE]\n\n"

    buf = SSEBuffer()
    events = buf.feed(ev1 + ev2 + ev3)
    assert len(events) == 3
    assert events[0] == ev1
    assert events[1] == ev2
    assert events[2] == ev3


# --------------------------------------------------------------------------- #
# TC-SSE-003: Residual content is flushed at stream end
# --------------------------------------------------------------------------- #
async def test_sse_buffer_flushes_residual_content():
    """TC-SSE-003: residual buffer content without trailing ``\\n\\n`` is
    flushed and returned so it is not silently dropped."""
    buf = SSEBuffer()
    residual_payload = 'data: {"choices":[{"delta":{"content":"tail"}}]}'
    events = buf.feed(residual_payload)  # no trailing \n\n
    assert events == []

    flushed = buf.flush()
    assert flushed is not None
    assert flushed == residual_payload
    # Buffer is cleared after flush.
    assert buf.flush() is None


async def test_sse_buffer_flush_done_marker_no_exception():
    """TC-SSE-003b: a ``[DONE]`` fragment in the residual is flushed without
    raising an exception."""
    buf = SSEBuffer()
    buf.feed("data: [DONE]")  # no trailing \n\n
    flushed = buf.flush()
    assert flushed is not None
    assert "[DONE]" in flushed


# --------------------------------------------------------------------------- #
# TC-SSE-004: Non-data events pass through unchanged
# --------------------------------------------------------------------------- #
async def test_sse_buffer_passes_through_non_data_events():
    """TC-SSE-004: ``event: safety_block`` and ``data: [DONE]`` events are
    reassembled and passed through with type and payload intact, even when
    mixed with data events in the same chunk."""
    safety_event = (
        'event: safety_block\ndata: {"blocked_by":"toxicity"}\n\n'
    )
    done_event = "data: [DONE]\n\n"
    data_event = _sse_data_event({"choices": [{"delta": {"content": "x"}}]})

    buf = SSEBuffer()
    # Mix all three in one chunk.
    events = buf.feed(safety_event + data_event + done_event)
    assert len(events) == 3
    assert events[0] == safety_event
    assert events[1] == data_event
    assert events[2] == done_event


async def test_sse_buffer_reassembles_split_non_data_event():
    """TC-SSE-004b: a split ``safety_block`` event is reassembled correctly."""
    full = 'event: safety_block\ndata: {"blocked_by":"x"}\n\n'
    mid = len(full) // 2
    buf = SSEBuffer()
    assert buf.feed(full[:mid]) == []
    events = buf.feed(full[mid:])
    assert len(events) == 1
    assert events[0] == full


# --------------------------------------------------------------------------- #
# TC-SSE-005: Reassembled event yields correct delta text for detection
# --------------------------------------------------------------------------- #
async def test_sse_buffer_reassembled_event_yields_delta_text():
    """TC-SSE-005: after reassembly, the complete event passed to
    ``_extract_delta_text`` yields the correct delta text, ensuring the
    content enters the sliding window instead of being judged empty."""
    original = _sse_data_event({"choices": [{"delta": {"content": "secret"}}]})
    mid = len(original) // 2

    buf = SSEBuffer()
    buf.feed(original[:mid])
    events = buf.feed(original[mid:])
    assert len(events) == 1

    delta = _extract_delta_text(events[0])
    assert delta == "secret"
