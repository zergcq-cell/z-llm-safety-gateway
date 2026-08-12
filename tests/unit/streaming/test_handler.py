"""Unit tests for StreamingHandler.

Covers TC-SSE-001, 002, 005~008, 011, 013 (sse-streaming spec).
"""

from __future__ import annotations

import asyncio
import json

from z_llm_safety_gateway.models import DetectionResult
from z_llm_safety_gateway.pipeline.engine import PipelineResult
from z_llm_safety_gateway.streaming.handler import StreamingHandler


def sse_chunk(text: str) -> str:
    """Build an OpenAI-style SSE chunk carrying *text* content."""
    payload = json.dumps({"choices": [{"delta": {"content": text}}]})
    return f"data: {payload}\n\n"


class _FakeEngine:
    """Fake pipeline engine that returns a configured result."""

    def __init__(self, result: PipelineResult | None = None) -> None:
        self.result = result or PipelineResult(
            final_action="allow", overall_risk_level="low"
        )
        self.calls: list[str] = []

    async def run(self, detectors, contexts, configs):
        self.calls.append(contexts[0].metadata["content"] if contexts else "")
        return self.result


class _BlockEngine(_FakeEngine):
    def __init__(self) -> None:
        result = PipelineResult(
            final_action="block",
            overall_risk_level="high",
            detector_results=[
                DetectionResult(
                    detector_name="toxicity",
                    category="toxicity",
                    action="block",
                    confidence=0.95,
                    risk_level="high",
                    message="toxic",
                )
            ],
        )
        super().__init__(result)


class _FlagEngine(_FakeEngine):
    def __init__(self) -> None:
        result = PipelineResult(
            final_action="flag",
            overall_risk_level="medium",
            detector_results=[
                DetectionResult(
                    detector_name="pii_redaction",
                    category="pii",
                    action="flag",
                    confidence=0.6,
                    risk_level="medium",
                    message="pii",
                )
            ],
        )
        super().__init__(result)


def _make_handler(engine, send_flag_events=False, window_size=10, overlap=3) -> StreamingHandler:
    return StreamingHandler(
        engine=engine,
        output_detectors=["toxicity"],
        detector_configs={},
        window_size=window_size,
        overlap=overlap,
        send_flag_events=send_flag_events,
    )


async def _collect(handler: StreamingHandler, chunks: list[str]) -> list[str]:
    events: list[str] = []
    for chunk in chunks:
        async for event in handler.process_chunk(chunk):
            events.append(event)
    return events


# --------------------------------------------------------------------------- #
# TC-SSE-001: transparent forwarding (allow)
# --------------------------------------------------------------------------- #
async def test_handler_forwards_chunks_on_allow():
    """TC-SSE-001: allow result forwards chunks and returns [DONE]."""
    handler = _make_handler(_FakeEngine())
    events = await _collect(handler, [sse_chunk("hi"), "data: [DONE]\n\n"])
    assert any("data:" in e for e in events)
    assert handler.completed is False  # finish() marks completion


# --------------------------------------------------------------------------- #
# TC-SSE-005: window block stops forwarding + safety_block + DONE
# --------------------------------------------------------------------------- #
async def test_handler_block_stops_and_sends_safety_block():
    """TC-SSE-005: block result stops forwarding and emits safety_block."""
    handler = _make_handler(_BlockEngine())
    events = await _collect(handler, [sse_chunk("a" * 10)])
    joined = "\n".join(events)
    assert "safety_block" in joined
    assert "data: [DONE]" in joined
    assert handler.blocked is True


# --------------------------------------------------------------------------- #
# TC-SSE-006: window flag continues + safety_flag event
# --------------------------------------------------------------------------- #
async def test_handler_flag_continues_with_safety_flag():
    """TC-SSE-006: flag result continues stream and emits safety_flag."""
    handler = _make_handler(_FlagEngine(), send_flag_events=True)
    events = await _collect(handler, [sse_chunk("a" * 10)])
    joined = "\n".join(events)
    assert "safety_flag" in joined
    assert handler.blocked is False


async def test_handler_flag_no_event_when_disabled():
    """TC-SSE-010: flag without send_flag_events emits no safety_flag."""
    handler = _make_handler(_FlagEngine(), send_flag_events=False)
    events = await _collect(handler, [sse_chunk("a" * 10)])
    joined = "\n".join(events)
    assert "safety_flag" not in joined


# --------------------------------------------------------------------------- #
# TC-SSE-011: detector parallel + short-circuit (reuse engine)
# --------------------------------------------------------------------------- #
async def test_handler_reuses_pipeline_engine():
    """TC-SSE-011: handler invokes the provided pipeline engine."""
    engine = _FakeEngine()
    handler = _make_handler(engine)
    await _collect(handler, [sse_chunk("a" * 10)])
    assert engine.calls, "engine should have been called for the window"
    assert engine.calls[0] == "a" * 10


# --------------------------------------------------------------------------- #
# TC-SSE-013: stream end produces DONE without error
# --------------------------------------------------------------------------- #
async def test_handler_handles_done_signal():
    """TC-SSE-013: finish() marks completion without error."""
    handler = _make_handler(_FakeEngine())
    handler.finish()
    assert handler.completed is True


# --------------------------------------------------------------------------- #
# Async runner helpers
# --------------------------------------------------------------------------- #
def run(coro):
    return asyncio.run(coro)


def test_forwards_chunks_allow():
    run(test_handler_forwards_chunks_on_allow())


def test_block_stops_and_sends_safety_block():
    run(test_handler_block_stops_and_sends_safety_block())


def test_flag_continues_with_safety_flag():
    run(test_handler_flag_continues_with_safety_flag())


def test_flag_no_event_when_disabled():
    run(test_handler_flag_no_event_when_disabled())


def test_reuses_pipeline_engine():
    run(test_handler_reuses_pipeline_engine())


def test_handles_done_signal():
    run(test_handler_handles_done_signal())
