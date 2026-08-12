"""Unit tests for SSE event formatting.

Covers TC-SSE-012 (sse-streaming spec).
"""

from __future__ import annotations

from z_llm_safety_gateway.streaming.sse import (
    SSE_DONE,
    format_chunk,
    format_safety_block,
    format_safety_flag,
)


# --------------------------------------------------------------------------- #
# TC-SSE-012: SSE event format
# --------------------------------------------------------------------------- #
def test_format_chunk():
    """TC-SSE-012: data: {chunk} format for standard chunks."""
    assert format_chunk('{"id":"1","choices":[{"delta":{"content":"hi"}}]}') == (
        'data: {"id":"1","choices":[{"delta":{"content":"hi"}}]}\n\n'
    )


def test_format_done():
    """TC-SSE-012b: data: [DONE] format."""
    assert SSE_DONE == "data: [DONE]\n\n"


def test_format_safety_block():
    """TC-SSE-012c: safety_block event includes required fields."""
    event = format_safety_block(
        request_id="req_abc123",
        blocked_by="toxicity",
        category="toxicity",
        risk_level="high",
        confidence=0.91,
        reason="Toxic content detected",
    )
    assert event.startswith("event: safety_block\n")
    assert "req_abc123" in event
    assert '"blocked_by": "toxicity"' in event
    assert '"category": "toxicity"' in event
    assert '"risk_level": "high"' in event
    assert '"confidence": 0.91' in event
    assert event.endswith("\n\n")


def test_format_safety_flag():
    """TC-SSE-012d: safety_flag event with aggregated flagged_by."""
    event = format_safety_flag(
        request_id="req_1",
        flagged_by="pii_redaction,toxicity",
        category="pii",
        risk_level="high",
        confidence=0.80,
        message="Multiple detectors flagged",
    )
    assert event.startswith("event: safety_flag\n")
    assert '"flagged_by": "pii_redaction,toxicity"' in event
    assert '"risk_level": "high"' in event
    assert event.endswith("\n\n")
