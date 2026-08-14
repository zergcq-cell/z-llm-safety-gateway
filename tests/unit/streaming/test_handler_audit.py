"""Unit tests for StreamingHandler audit fields and PostAuditRunner passthrough.

Covers TC-SSE-006 ~ TC-SSE-015 (sse-streaming spec, B-05/B-06/B-07,
Decision 15).
"""

from __future__ import annotations

import json
from typing import Any

from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.pipeline.engine import PipelineResult
from z_llm_safety_gateway.post_audit.audit import PostAuditRunner
from z_llm_safety_gateway.streaming.handler import StreamingHandler

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sse_chunk(text: str) -> str:
    """Build an OpenAI-style SSE chunk carrying *text* content."""
    payload = json.dumps({"choices": [{"delta": {"content": text}}]})
    return f"data: {payload}\n\n"


class _FakeEngine:
    """Fake pipeline engine with configurable sequential results.

    Returns ``results[index]`` on the *index*-th call, then ``allow`` forever.
    Captures every DetectionContext for later assertions.
    """

    def __init__(self, results: list[PipelineResult] | None = None) -> None:
        self._results = results or []
        self._index = 0
        self.contexts: list[DetectionContext] = []

    async def run(
        self,
        detectors: list[Any],
        contexts: list[DetectionContext],
        configs: dict[str, dict[str, Any]],
    ) -> PipelineResult:
        self.contexts.extend(contexts)
        if self._index < len(self._results):
            result = self._results[self._index]
            self._index += 1
            return result
        return PipelineResult(final_action="allow", overall_risk_level="low")


def _flag_result() -> PipelineResult:
    return PipelineResult(
        final_action="flag",
        overall_risk_level="medium",
        detector_results=[
            DetectionResult(
                detector_name="pii_redaction",
                category="pii",
                action="flag",
                confidence=0.6,
                risk_level="medium",
                message="pii detected",
            )
        ],
    )


def _block_result() -> PipelineResult:
    return PipelineResult(
        final_action="block",
        overall_risk_level="high",
        detector_results=[
            DetectionResult(
                detector_name="toxicity",
                category="toxicity",
                action="block",
                confidence=0.95,
                risk_level="high",
                message="toxic content",
            )
        ],
    )


def _allow_result() -> PipelineResult:
    return PipelineResult(
        final_action="allow",
        overall_risk_level="low",
        detector_results=[
            DetectionResult(
                detector_name="toxicity",
                category="toxicity",
                action="allow",
                confidence=0.1,
                risk_level="low",
                message="safe",
            )
        ],
    )


def _make_handler(
    engine: _FakeEngine,
    *,
    window_size: int = 10,
    overlap: int = 3,
    send_flag_events: bool = False,
    request_id: str = "",
    language: str | None = None,
) -> StreamingHandler:
    return StreamingHandler(
        engine=engine,
        output_detectors=["toxicity"],
        detector_configs={},
        window_size=window_size,
        overlap=overlap,
        send_flag_events=send_flag_events,
        request_id=request_id,
        language=language,
    )


async def _collect(handler: StreamingHandler, chunks: list[str]) -> list[str]:
    events: list[str] = []
    for chunk in chunks:
        async for event in handler.process_chunk(chunk):
            events.append(event)
    # Drain residual SSE buffer content at stream end.
    async for event in handler.drain():
        events.append(event)
    return events


# --------------------------------------------------------------------------- #
# TC-SSE-006: handler aggregates output_action by severity
# --------------------------------------------------------------------------- #
async def test_handler_aggregates_output_action_by_severity():
    """TC-SSE-006: output_action is aggregated by severity
    (allow < flag < modify < block) across multiple windows."""
    engine = _FakeEngine([_allow_result(), _flag_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    await _collect(handler, [sse_chunk("a" * 10), sse_chunk("b" * 10)])

    assert handler.output_action == "flag"


async def test_handler_output_action_escalates_to_block():
    """TC-SSE-006b: output_action escalates to block when a window blocks."""
    engine = _FakeEngine([_allow_result(), _block_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    await _collect(handler, [sse_chunk("a" * 10), sse_chunk("b" * 10)])

    assert handler.output_action == "block"


# --------------------------------------------------------------------------- #
# TC-SSE-007: handler output_risk_level takes the highest across windows
# --------------------------------------------------------------------------- #
async def test_handler_output_risk_level_takes_highest():
    """TC-SSE-007: output_risk_level is the highest risk level across all
    detected windows."""
    engine = _FakeEngine([
        PipelineResult(
            final_action="allow",
            overall_risk_level="low",
            detector_results=[
                DetectionResult(
                    detector_name="d1",
                    category="cat",
                    action="allow",
                    confidence=0.1,
                    risk_level="low",
                    message="ok",
                )
            ],
        ),
        PipelineResult(
            final_action="flag",
            overall_risk_level="high",
            detector_results=[
                DetectionResult(
                    detector_name="d2",
                    category="cat",
                    action="flag",
                    confidence=0.7,
                    risk_level="high",
                    message="flagged",
                )
            ],
        ),
    ])
    handler = _make_handler(engine, window_size=10, overlap=3)
    await _collect(handler, [sse_chunk("a" * 10), sse_chunk("b" * 10)])

    assert handler.output_risk_level == "high"


# --------------------------------------------------------------------------- #
# TC-SSE-008: block mid-stream sets output_action=block + detector_results
# --------------------------------------------------------------------------- #
async def test_handler_block_records_output_state_and_detectors():
    """TC-SSE-008: when a window blocks, output_action=block,
    output_risk_level reflects the blocking window, and detector_results
    contains the blocking detector's result."""
    engine = _FakeEngine([_block_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    await _collect(handler, [sse_chunk("a" * 10)])

    assert handler.output_action == "block"
    assert handler.output_risk_level == "high"
    assert handler.blocked is True
    # detector_results should contain the blocking detector.
    names = [r.detector_name for r in handler.detector_results]
    assert "toxicity" in names


# --------------------------------------------------------------------------- #
# TC-SSE-009: handler output_action is independent of input-side state
# --------------------------------------------------------------------------- #
async def test_handler_output_action_independent_of_input_side():
    """TC-SSE-009: the handler's output_action is derived solely from output
    window detection results, not from any input-side request.state value.
    Even when the handler is constructed without any input-side context,
    output_action reflects the actual window results."""
    engine = _FakeEngine([_block_result()])
    # No input-side state is set on the handler at all.
    handler = _make_handler(engine, window_size=10, overlap=3, request_id="req-1")
    await _collect(handler, [sse_chunk("a" * 10)])

    # Output-side should be block, independently of input.
    assert handler.output_action == "block"
    assert handler.output_risk_level == "high"


# --------------------------------------------------------------------------- #
# TC-SSE-010: PostAuditRunner.run returns detector_results in the outcome
# --------------------------------------------------------------------------- #
async def test_post_audit_returns_detector_results():
    """TC-SSE-010: PostAuditOutcome.detector_results contains the full
    detector results from the post-audit pass (SC-SSE-008)."""
    block_result = PipelineResult(
        final_action="block",
        overall_risk_level="critical",
        detector_results=[
            DetectionResult(
                detector_name="secret_leak",
                category="secret",
                action="block",
                confidence=0.99,
                risk_level="critical",
                message="API key leaked",
            )
        ],
    )
    engine = _FakeEngine([block_result])
    runner = PostAuditRunner(
        engine=engine, output_detectors=["secret_leak"], detector_configs={}
    )
    outcome = await runner.run("some secret content")

    assert outcome.detector_results is not None
    assert len(outcome.detector_results) == 1
    assert outcome.detector_results[0].detector_name == "secret_leak"
    assert outcome.detector_results[0].action == "block"


# --------------------------------------------------------------------------- #
# TC-SSE-011: handler window_count increments per detected window
# --------------------------------------------------------------------------- #
async def test_handler_window_count_increments():
    """TC-SSE-011: window_count equals the number of windows actually
    detected during the streaming session (SC-SSE-009)."""
    engine = _FakeEngine([_allow_result(), _allow_result(), _allow_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    # Three full windows: 30 chars total, each chunk = 10 chars.
    await _collect(handler, [sse_chunk("a" * 10) for _ in range(3)])

    assert handler.window_count == 3


async def test_handler_window_count_zero_when_no_windows():
    """TC-SSE-011b: window_count is 0 when no window reached window_size."""
    engine = _FakeEngine()
    handler = _make_handler(engine, window_size=100, overlap=10)
    await _collect(handler, [sse_chunk("short"), "data: [DONE]\n\n"])

    assert handler.window_count == 0


# --------------------------------------------------------------------------- #
# TC-SSE-012: PostAuditRunner.run passes request_id to DetectionContext
# --------------------------------------------------------------------------- #
async def test_post_audit_passes_request_id():
    """TC-SSE-012: PostAuditRunner.run accepts request_id and passes it
    to the DetectionContext (SC-SSE-010)."""
    engine = _FakeEngine()
    runner = PostAuditRunner(
        engine=engine, output_detectors=["secret_leak"], detector_configs={}
    )
    await runner.run("content", request_id="req-abc-123")

    assert engine.contexts[0].request_id == "req-abc-123"


async def test_post_audit_request_id_defaults_empty():
    """TC-SSE-012b: when request_id is not provided, it defaults to empty
    string (backward-compatible)."""
    engine = _FakeEngine()
    runner = PostAuditRunner(
        engine=engine, output_detectors=["secret_leak"], detector_configs={}
    )
    await runner.run("content")

    assert engine.contexts[0].request_id == ""


# --------------------------------------------------------------------------- #
# TC-SSE-013: handler passes language to DetectionContext
# --------------------------------------------------------------------------- #
async def test_handler_passes_language_to_context():
    """TC-SSE-013: handler accepts language and passes it to the
    DetectionContext used for window detection (SC-SSE-011)."""
    engine = _FakeEngine([_allow_result()])
    handler = _make_handler(engine, window_size=10, overlap=3, language="zh")
    await _collect(handler, [sse_chunk("a" * 10)])

    assert engine.contexts[0].language == "zh"


async def test_handler_language_defaults_none():
    """TC-SSE-013b: when language is not provided, DetectionContext.language
    is None (no fake value)."""
    engine = _FakeEngine([_allow_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    await _collect(handler, [sse_chunk("a" * 10)])

    assert engine.contexts[0].language is None


# --------------------------------------------------------------------------- #
# TC-SSE-014: handler exposes language for audit entry construction
# --------------------------------------------------------------------------- #
async def test_handler_exposes_language_property():
    """TC-SSE-014: handler.language returns the input-side language for
    use in the streaming audit entry (SC-SSE-012)."""
    handler_with = _make_handler(_FakeEngine(), language="en")
    assert handler_with.language == "en"

    handler_without = _make_handler(_FakeEngine())
    assert handler_without.language is None


# --------------------------------------------------------------------------- #
# TC-SSE-015: error path — handler defaults reflect actual (no fake block)
# --------------------------------------------------------------------------- #
async def test_handler_defaults_when_no_detection_ran():
    """TC-SSE-015: when no windows were processed (e.g. provider error
    before any window), output_action=allow, output_risk_level=low,
    window_count=0, and detector_results is empty — no fabricated block."""
    handler = _make_handler(_FakeEngine(), window_size=10, overlap=3)

    assert handler.output_action == "allow"
    assert handler.output_risk_level == "low"
    assert handler.window_count == 0
    assert handler.detector_results == []


async def test_handler_partial_results_before_error():
    """TC-SSE-015b: if some windows processed before an error, output state
    reflects those windows (not fabricated)."""
    engine = _FakeEngine([_flag_result()])
    handler = _make_handler(engine, window_size=10, overlap=3)
    # Process one window, then simulate stream end (no more chunks).
    await _collect(handler, [sse_chunk("a" * 10)])

    assert handler.output_action == "flag"
    assert handler.output_risk_level == "medium"
    assert handler.window_count == 1
    assert len(handler.detector_results) == 1
