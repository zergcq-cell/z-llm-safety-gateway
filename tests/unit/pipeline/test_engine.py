"""Unit tests for PipelineEngine — TC-PIPE-001 through TC-PIPE-012.

Covers the parallel pipeline execution engine as specified in pipeline-engine/
spec.yaml and design.md Decision 1.

Test areas:
- TC-PIPE-001: Parallel execution of multiple detectors
- TC-PIPE-002: Block short-circuit cancels remaining tasks
- TC-PIPE-003: Result aggregation (final_action priority)
- TC-PIPE-004: overall_risk_level takes highest
- TC-PIPE-005: pipeline_duration_ms is recorded
- TC-PIPE-006: block_and_modify short-circuit
- TC-PIPE-007: block mode does not short-circuit on modify
- TC-PIPE-009: modifications sorted by priority
- TC-PIPE-010: fail_open error handling
- TC-PIPE-011: fail_closed error handling
- TC-PIPE-012: per-detector timeout
- Circuit breaker integration

All tests use mock Detector subclasses — no real detectors are loaded.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from z_llm_safety_gateway.circuit_breaker import CircuitBreaker
from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult

# --------------------------------------------------------------------------- #
# Mock detectors
# --------------------------------------------------------------------------- #


class _MockDetector:
    """A configurable async mock detector for pipeline testing.

    This class duck-types as a Detector — it provides the same async
    interface (initialize, detect, health_check, shutdown) and class
    attributes (name, category, description, version) without inheriting
    from the Detector ABC, allowing per-instance configuration of name.
    """

    description: str = "Mock detector for testing"
    version: str = "1.0.0"

    def __init__(
        self,
        name: str = "mock",
        confidence: float = 0.0,
        risk_level: str = "low",
        modified_content: str | None = None,
        delay: float = 0.0,
        raise_error: BaseException | None = None,
        category: str = "test",
    ) -> None:
        self.name = name
        self.category = category
        self._confidence = confidence
        self._risk_level = risk_level
        self._modified_content = modified_content
        self._delay = delay
        self._raise_error = raise_error
        self.detect_called: bool = False
        self.completed: bool = False

    async def initialize(self, config: dict[str, Any]) -> None:
        pass

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        self.detect_called = True
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._raise_error is not None:
            raise self._raise_error
        self.completed = True
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",  # engine overrides via threshold
            confidence=self._confidence,
            risk_level=self._risk_level,
            message="mock detection result",
            modified_content=self._modified_content,
        )

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass


# Type alias for the mock detector (satisfies type checkers expecting Detector).
_MockDetectorT = Any


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _context(
    content: str = "hello world",
    direction: str = "input",
    request_id: str = "req-1",
    message_index: int | None = 0,
) -> DetectionContext:
    """Create a DetectionContext with content stored in metadata."""
    return DetectionContext(
        direction=direction,  # type: ignore[arg-type]
        request_id=request_id,
        message_index=message_index,
        metadata={"content": content},
    )


def _default_configs(
    block_threshold: float = 0.85,
    flag_threshold: float = 0.50,
) -> dict[str, dict[str, Any]]:
    """Default detector config with standard thresholds."""
    return {
        "det_a": {
            "priority": 10,
            "on_error": "fail_open",
            "block_threshold": block_threshold,
            "flag_threshold": flag_threshold,
        },
        "det_b": {
            "priority": 20,
            "on_error": "fail_open",
            "block_threshold": block_threshold,
            "flag_threshold": flag_threshold,
        },
        "det_c": {
            "priority": 30,
            "on_error": "fail_open",
            "block_threshold": block_threshold,
            "flag_threshold": flag_threshold,
        },
    }


# --------------------------------------------------------------------------- #
# TC-PIPE-001: Parallel execution
# --------------------------------------------------------------------------- #


class TestParallelExecution:
    """REQ-001 SC-001: All enabled detectors run in parallel."""

    async def test_all_detectors_executed(self) -> None:
        """TC-PIPE-001: All 3 detectors are executed when run() is called."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.3),
            _MockDetector(name="det_b", confidence=0.3),
            _MockDetector(name="det_c", confidence=0.3),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert all(d.detect_called for d in detectors)
        assert len(result.detector_results) == 3

    async def test_detectors_run_concurrently(self) -> None:
        """Detectors run in parallel — total time < sum of individual delays."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.3, delay=0.05),
            _MockDetector(name="det_b", confidence=0.3, delay=0.05),
            _MockDetector(name="det_c", confidence=0.3, delay=0.05),
        ]
        engine = PipelineEngine()
        start = time.monotonic()
        await engine.run(detectors, [_context()], _default_configs())
        elapsed = time.monotonic() - start

        # If parallel, elapsed ≈ 0.05s, not 0.15s
        assert elapsed < 0.12

    async def test_priority_does_not_affect_execution_order(self) -> None:
        """Priority only affects modification order, not execution start."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.3, delay=0.01),
            _MockDetector(name="det_b", confidence=0.3, delay=0.01),
        ]
        configs = _default_configs()
        configs["det_a"]["priority"] = 99  # lower priority (higher number)
        configs["det_b"]["priority"] = 1   # higher priority (lower number)

        engine = PipelineEngine()
        await engine.run(detectors, [_context()], configs)

        # Both detectors should be called regardless of priority
        assert detectors[0].detect_called
        assert detectors[1].detect_called


# --------------------------------------------------------------------------- #
# TC-PIPE-002: Block short-circuit
# --------------------------------------------------------------------------- #


class TestBlockShortCircuit:
    """REQ-002 SC-001: Block result triggers short-circuit cancellation."""

    async def test_block_cancels_remaining_tasks(self) -> None:
        """TC-PIPE-002: A block result cancels other running detectors."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90, delay=0.01),  # block
            _MockDetector(name="det_b", confidence=0.30, delay=0.50),  # slow
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "block"
        # det_a completed, det_b was cancelled
        assert detectors[0].completed
        assert not detectors[1].completed
        # Only det_a's result is collected
        assert len(result.detector_results) == 1
        assert result.detector_results[0].detector_name == "det_a"

    async def test_block_short_circuit_is_fast(self) -> None:
        """Short-circuit does not wait for slow detectors."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90, delay=0.01),  # block fast
            _MockDetector(name="det_b", confidence=0.30, delay=1.00),  # very slow
        ]
        engine = PipelineEngine()
        start = time.monotonic()
        await engine.run(detectors, [_context()], _default_configs())
        elapsed = time.monotonic() - start

        # Should finish well under 1 second
        assert elapsed < 0.5

    async def test_block_result_in_detector_results(self) -> None:
        """The block result is collected into detector_results."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90),  # block
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert len(result.detector_results) == 1
        assert result.detector_results[0].action == "block"

    async def test_multiple_blocks_only_first_collected(self) -> None:
        """When two detectors return block, at most the completed ones are collected."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90, delay=0.01),
            _MockDetector(name="det_b", confidence=0.90, delay=0.02),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "block"
        # At least one block result is collected
        block_results = [r for r in result.detector_results if r.action == "block"]
        assert len(block_results) >= 1


# --------------------------------------------------------------------------- #
# TC-PIPE-006/007: block_and_modify short-circuit
# --------------------------------------------------------------------------- #


class TestModifyShortCircuit:
    """REQ-003 SC-001/002: Modify short-circuit in block_and_modify mode."""

    async def test_modify_triggers_short_circuit_in_block_and_modify_mode(self) -> None:
        """TC-PIPE-006: modify triggers short-circuit when short_circuit_on=block_and_modify."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(
                name="det_a",
                confidence=0.0,
                modified_content="redacted",
                delay=0.01,
            ),
            _MockDetector(name="det_b", confidence=0.30, delay=0.50),
        ]
        engine = PipelineEngine(short_circuit_on="block_and_modify")
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "modify"
        assert detectors[0].completed
        assert not detectors[1].completed
        assert len(result.detector_results) == 1

    async def test_modify_does_not_short_circuit_in_block_mode(self) -> None:
        """TC-PIPE-007: modify does NOT short-circuit when short_circuit_on=block."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(
                name="det_a",
                confidence=0.0,
                modified_content="redacted",
                delay=0.01,
            ),
            _MockDetector(name="det_b", confidence=0.30, delay=0.01),
        ]
        engine = PipelineEngine(short_circuit_on="block")
        result = await engine.run(detectors, [_context()], _default_configs())

        # Both detectors should complete
        assert detectors[0].completed
        assert detectors[1].completed
        assert len(result.detector_results) == 2
        assert result.final_action == "modify"

    async def test_block_triggers_short_circuit_in_block_and_modify_mode(self) -> None:
        """Block also triggers short-circuit in block_and_modify mode."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90, delay=0.01),
            _MockDetector(name="det_b", confidence=0.30, delay=0.50),
        ]
        engine = PipelineEngine(short_circuit_on="block_and_modify")
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "block"
        assert not detectors[1].completed


# --------------------------------------------------------------------------- #
# TC-PIPE-003/004/008: Result aggregation
# --------------------------------------------------------------------------- #


class TestResultAggregation:
    """REQ-004/005 SC-001/002: Engine aggregates results correctly."""

    async def test_all_allow_returns_allow(self) -> None:
        """All detectors return allow → final_action = allow."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
            _MockDetector(name="det_b", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "allow"

    async def test_flag_plus_allow_returns_flag(self) -> None:
        """TC-PIPE-008: flag + allow → final_action = flag."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.60),  # flag
            _MockDetector(name="det_b", confidence=0.30),  # allow
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "flag"

    async def test_block_plus_others_returns_block(self) -> None:
        """block takes precedence over all other actions."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),   # allow
            _MockDetector(name="det_b", confidence=0.60),   # flag
            _MockDetector(name="det_c", confidence=0.90),   # block
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "block"

    async def test_overall_risk_level_takes_highest(self) -> None:
        """TC-PIPE-004: overall_risk_level = highest among all results."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, risk_level="low"),
            _MockDetector(name="det_b", confidence=0.60, risk_level="medium"),
            _MockDetector(name="det_c", confidence=0.30, risk_level="high"),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.overall_risk_level == "high"

    async def test_overall_risk_level_critical(self) -> None:
        """Critical risk level is the highest."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, risk_level="low"),
            _MockDetector(name="det_b", confidence=0.90, risk_level="critical"),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.overall_risk_level == "critical"

    async def test_risk_level_reflects_even_when_allow(self) -> None:
        """overall_risk_level reflects highest risk even when final_action is allow."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, risk_level="high"),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.final_action == "allow"
        assert result.overall_risk_level == "high"


# --------------------------------------------------------------------------- #
# TC-PIPE-009: Modifications sorting
# --------------------------------------------------------------------------- #


class TestModificationsCollection:
    """REQ-006 SC-001: Modifications collected from modify results, sorted by priority."""

    async def test_modifications_sorted_by_priority(self) -> None:
        """TC-PIPE-009: modifications sorted by detector priority ascending."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(
                name="det_b",
                confidence=0.0,
                modified_content="b_content",
            ),
            _MockDetector(
                name="det_a",
                confidence=0.0,
                modified_content="a_content",
            ),
        ]
        configs = _default_configs()
        configs["det_a"]["priority"] = 10
        configs["det_b"]["priority"] = 20

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        assert len(result.modifications) == 2
        # det_a (priority=10) before det_b (priority=20)
        assert result.modifications[0].detector_name == "det_a"
        assert result.modifications[1].detector_name == "det_b"

    async def test_modifications_include_message_index(self) -> None:
        """Modifications carry the message_index from the DetectionContext."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(
                name="det_a",
                confidence=0.0,
                modified_content="redacted",
            ),
        ]
        engine = PipelineEngine()
        result = await engine.run(
            detectors,
            [_context(message_index=3)],
            _default_configs(),
        )

        assert len(result.modifications) == 1
        assert result.modifications[0].message_index == 3

    async def test_no_modifications_when_all_allow(self) -> None:
        """No modifications when no detector returns modify."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert len(result.modifications) == 0


# --------------------------------------------------------------------------- #
# TC-PIPE-010/011: Error handling (fail_open / fail_closed)
# --------------------------------------------------------------------------- #


class TestErrorHandling:
    """REQ-008 SC-001/002: Detector exceptions handled via on_error strategy."""

    async def test_fail_open_skips_failing_detector(self) -> None:
        """TC-PIPE-010: fail_open skips the detector, continues processing."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=RuntimeError("boom")),
            _MockDetector(name="det_b", confidence=0.30),
        ]
        configs = _default_configs()
        configs["det_a"]["on_error"] = "fail_open"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        # det_a failed → allow (skipped), det_b → allow
        assert result.final_action == "allow"
        assert len(result.detector_results) == 2

        # det_a's result should have error set and action=allow
        det_a_result = next(
            r for r in result.detector_results if r.detector_name == "det_a"
        )
        assert det_a_result.action == "allow"
        assert det_a_result.error is not None
        assert "boom" in det_a_result.error

    async def test_fail_open_other_detectors_unaffected(self) -> None:
        """fail_open: other detectors continue and are not affected."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=RuntimeError("boom")),
            _MockDetector(name="det_b", confidence=0.90),  # block
        ]
        configs = _default_configs()
        configs["det_a"]["on_error"] = "fail_open"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        # det_b's block should still be reflected
        assert result.final_action == "block"

    async def test_fail_closed_blocks_request(self) -> None:
        """TC-PIPE-011: fail_closed sets action=block for the failing detector."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=RuntimeError("boom")),
            _MockDetector(name="det_b", confidence=0.30, delay=0.50),
        ]
        configs = _default_configs()
        configs["det_a"]["on_error"] = "fail_closed"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        assert result.final_action == "block"

        det_a_result = next(
            r for r in result.detector_results if r.detector_name == "det_a"
        )
        assert det_a_result.action == "block"
        assert det_a_result.error is not None
        assert "boom" in det_a_result.error

        # det_b should have been short-circuited (fail_closed → block)
        assert not detectors[1].completed

    async def test_fail_closed_error_in_result(self) -> None:
        """fail_closed: the error message is stored in DetectionResult.error."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=ValueError("bad value")),
        ]
        configs = _default_configs()
        configs["det_a"]["on_error"] = "fail_closed"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        det_a_result = result.detector_results[0]
        assert det_a_result.error == "bad value"

    async def test_fail_open_error_result_has_duration(self) -> None:
        """Error results include duration_ms."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=RuntimeError("boom")),
        ]
        configs = _default_configs()
        configs["det_a"]["on_error"] = "fail_open"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        det_a_result = result.detector_results[0]
        assert det_a_result.duration_ms >= 0.0


# --------------------------------------------------------------------------- #
# TC-PIPE-012: Per-detector timeout
# --------------------------------------------------------------------------- #


class TestTimeoutHandling:
    """REQ-009 SC-001: Per-detector timeout handled via on_error strategy."""

    async def test_timeout_fail_open(self) -> None:
        """TC-PIPE-012: Timeout with fail_open → detector skipped (allow)."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=1.0),  # slow
            _MockDetector(name="det_b", confidence=0.30, delay=0.01),
        ]
        configs = _default_configs()
        configs["det_a"]["timeout_seconds"] = 0.05
        configs["det_a"]["on_error"] = "fail_open"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        # det_a timed out → fail_open → allow
        # det_b → allow
        assert result.final_action == "allow"

        det_a_result = next(
            r for r in result.detector_results if r.detector_name == "det_a"
        )
        assert det_a_result.action == "allow"
        assert det_a_result.error is not None
        assert "timed out" in det_a_result.error.lower()

    async def test_timeout_fail_closed(self) -> None:
        """Timeout with fail_closed → block."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=1.0),
        ]
        configs = _default_configs()
        configs["det_a"]["timeout_seconds"] = 0.05
        configs["det_a"]["on_error"] = "fail_closed"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        assert result.final_action == "block"

        det_a_result = result.detector_results[0]
        assert det_a_result.action == "block"
        assert det_a_result.error is not None
        assert "timed out" in det_a_result.error.lower()

    async def test_timeout_duration_recorded(self) -> None:
        """Timeout result includes duration_ms reflecting wait time."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=1.0),
        ]
        configs = _default_configs()
        configs["det_a"]["timeout_seconds"] = 0.1
        configs["det_a"]["on_error"] = "fail_open"

        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        det_a_result = result.detector_results[0]
        # duration should be around 0.1s (100ms)
        assert det_a_result.duration_ms > 50.0  # at least 50ms
        assert det_a_result.duration_ms < 500.0  # less than 500ms


# --------------------------------------------------------------------------- #
# TC-PIPE-005: pipeline_duration_ms
# --------------------------------------------------------------------------- #


class TestPipelineDuration:
    """REQ-010 SC-001: pipeline_duration_ms is recorded."""

    async def test_duration_is_positive_float(self) -> None:
        """TC-PIPE-005: pipeline_duration_ms is a positive float."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert isinstance(result.pipeline_duration_ms, float)
        assert result.pipeline_duration_ms > 0.0

    async def test_duration_reflects_execution_time(self) -> None:
        """pipeline_duration_ms roughly matches the execution time."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=0.1),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        # Should be at least 100ms (the delay)
        assert result.pipeline_duration_ms >= 90.0

    async def test_duration_reflects_short_circuit_time(self) -> None:
        """Short-circuit scenario: duration reflects time to short-circuit."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.90, delay=0.02),  # block fast
            _MockDetector(name="det_b", confidence=0.30, delay=2.0),   # very slow
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        # Should be well under 2 seconds (short-circuited)
        assert result.pipeline_duration_ms < 500.0


# --------------------------------------------------------------------------- #
# PipelineResult model
# --------------------------------------------------------------------------- #


class TestPipelineResult:
    """PipelineResult data model has correct fields."""

    def test_default_values(self) -> None:
        """PipelineResult has sensible defaults."""
        result = PipelineResult()
        assert result.final_action == "allow"
        assert result.overall_risk_level == "low"
        assert result.detector_results == []
        assert result.modifications == []
        assert result.pipeline_duration_ms == 0.0

    def test_is_pydantic_model(self) -> None:
        """PipelineResult is a Pydantic BaseModel instance."""
        result = PipelineResult()
        assert hasattr(result, "model_dump")


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #


class TestEdgeCases:
    """Edge case handling."""

    async def test_no_detectors(self) -> None:
        """No detectors → final_action = allow."""
        engine = PipelineEngine()
        result = await engine.run([], [_context()], {})

        assert result.final_action == "allow"
        assert len(result.detector_results) == 0

    async def test_no_contexts(self) -> None:
        """No contexts → final_action = allow."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [], _default_configs())

        assert result.final_action == "allow"
        assert len(result.detector_results) == 0
        assert not detectors[0].detect_called

    async def test_multiple_contexts(self) -> None:
        """Multiple contexts: each detector runs on each context."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(
            detectors,
            [_context(message_index=0), _context(message_index=1)],
            _default_configs(),
        )

        # 1 detector × 2 contexts = 2 results
        assert len(result.detector_results) == 2

    async def test_invalid_short_circuit_on_raises(self) -> None:
        """Invalid short_circuit_on value raises ValueError."""
        with pytest.raises(ValueError):
            PipelineEngine(short_circuit_on="invalid")  # type: ignore[arg-type]

    async def test_default_config_used_when_missing(self) -> None:
        """Detector without config entry uses defaults."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="unknown_det", confidence=0.30),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], {})

        # With default thresholds (1.0, 1.0), confidence 0.30 → allow
        assert result.final_action == "allow"


# --------------------------------------------------------------------------- #
# Circuit breaker integration
# --------------------------------------------------------------------------- #


class TestCircuitBreakerIntegration:
    """Circuit breaker: open breaker skips detector with fallback action."""

    async def test_open_breaker_fail_open_skips_detector(self) -> None:
        """Open breaker with fail_open → detector skipped (allow)."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=999.0,
            fallback_action="fail_open",
        )
        breaker.record_failure()  # trip to OPEN
        assert breaker.is_open()

        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        configs = {
            "det_a": {
                "priority": 10,
                "on_error": "fail_open",
                "block_threshold": 0.85,
                "flag_threshold": 0.50,
                "circuit_breaker": breaker,
            }
        }
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        # Detector was NOT called (breaker open)
        assert not detectors[0].detect_called
        # Fallback result is allow
        assert result.final_action == "allow"
        assert len(result.detector_results) == 1
        assert result.detector_results[0].action == "allow"
        assert result.detector_results[0].error is not None

    async def test_open_breaker_fail_closed_blocks(self) -> None:
        """Open breaker with fail_closed → block."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=999.0,
            fallback_action="fail_closed",
        )
        breaker.record_failure()

        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=0.50),
        ]
        configs = {
            "det_a": {
                "priority": 10,
                "on_error": "fail_open",
                "block_threshold": 0.85,
                "flag_threshold": 0.50,
                "circuit_breaker": breaker,
            }
        }
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        assert result.final_action == "block"
        assert not detectors[0].detect_called

    async def test_closed_breaker_allows_execution(self) -> None:
        """Closed breaker allows normal detector execution."""
        breaker = CircuitBreaker(failure_threshold=5, fallback_action="fail_open")

        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        configs = {
            "det_a": {
                "priority": 10,
                "on_error": "fail_open",
                "block_threshold": 0.85,
                "flag_threshold": 0.50,
                "circuit_breaker": breaker,
            }
        }
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], configs)

        assert detectors[0].detect_called
        assert result.final_action == "allow"

    async def test_successful_detect_records_success(self) -> None:
        """A successful detect() call records success on the breaker."""
        breaker = CircuitBreaker(failure_threshold=3, fallback_action="fail_open")
        # Add some failures but don't trip
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30),
        ]
        configs = {
            "det_a": {
                "priority": 10,
                "on_error": "fail_open",
                "block_threshold": 0.85,
                "flag_threshold": 0.50,
                "circuit_breaker": breaker,
            }
        }
        engine = PipelineEngine()
        await engine.run(detectors, [_context()], configs)

        # Success should have reset the failure count
        assert breaker.failure_count == 0

    async def test_failed_detect_records_failure(self) -> None:
        """A failed detect() call records failure on the breaker."""
        breaker = CircuitBreaker(failure_threshold=5, fallback_action="fail_open")

        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", raise_error=RuntimeError("boom")),
        ]
        configs = {
            "det_a": {
                "priority": 10,
                "on_error": "fail_open",
                "block_threshold": 0.85,
                "flag_threshold": 0.50,
                "circuit_breaker": breaker,
            }
        }
        engine = PipelineEngine()
        await engine.run(detectors, [_context()], configs)

        assert breaker.failure_count == 1


# --------------------------------------------------------------------------- #
# Per-detector duration_ms
# --------------------------------------------------------------------------- #


class TestPerDetectorDuration:
    """Each DetectionResult has duration_ms set by the engine."""

    async def test_duration_ms_recorded_per_detector(self) -> None:
        """Each result has a non-negative duration_ms."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=0.02),
            _MockDetector(name="det_b", confidence=0.30, delay=0.01),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        for r in result.detector_results:
            assert r.duration_ms >= 0.0

    async def test_duration_ms_reflects_delay(self) -> None:
        """A detector with 50ms delay has duration_ms >= 40ms."""
        detectors: list[_MockDetectorT] = [
            _MockDetector(name="det_a", confidence=0.30, delay=0.05),
        ]
        engine = PipelineEngine()
        result = await engine.run(detectors, [_context()], _default_configs())

        assert result.detector_results[0].duration_ms >= 40.0
