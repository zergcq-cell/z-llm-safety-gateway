"""Pipeline engine — parallel detector execution with short-circuit cancellation.

Implements the core pipeline execution engine as specified in DESIGN.md
Section 5.1 and design.md Decision 1.

Key behaviours:

- Creates one :class:`asyncio.Task` per ``(context, detector)`` pair.
- Monitors completion via ``asyncio.wait(return_when=FIRST_COMPLETED)``.
- Short-circuits on ``block`` (always) or ``modify`` (when
  ``short_circuit_on="block_and_modify"``), cancelling all pending tasks.
- Applies per-detector ``timeout`` via :func:`asyncio.wait_for`.
- Handles detector exceptions via ``on_error`` strategy (fail_open / fail_closed).
- Integrates :class:`~z_llm_safety_gateway.circuit_breaker.CircuitBreaker` when
  configured — open breakers skip the detector and apply ``fallback_action``.
- Records ``duration_ms`` per detector and ``pipeline_duration_ms`` overall.
- Uses :class:`~z_llm_safety_gateway.pipeline.threshold.ThresholdDecisionEngine`
  to map confidence → action, keeping the action-decision outside detectors.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, Field

from z_llm_safety_gateway.circuit_breaker import CircuitBreaker
from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult, Modification
from z_llm_safety_gateway.pipeline.aggregator import ResultAggregator
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule
from z_llm_safety_gateway.pipeline.threshold import ThresholdDecisionEngine

logger = structlog.get_logger(__name__)

# Default config values used when a detector name has no entry in
# ``detector_configs`` or when individual keys are missing.
_DEFAULT_PRIORITY = 100
_DEFAULT_ON_ERROR = "fail_open"
_DEFAULT_BLOCK_THRESHOLD = 1.0
_DEFAULT_FLAG_THRESHOLD = 1.0


class PipelineResult(BaseModel):
    """The outcome of a :meth:`PipelineEngine.run` call.

    Attributes:
        final_action: Aggregated action (block > modify > flag > allow).
        overall_risk_level: Highest risk level across all detector results.
        detector_results: All collected DetectionResults (excluding cancelled).
        modifications: Modify results converted to Modification objects,
            sorted by detector priority.
        pipeline_duration_ms: Wall-clock duration of the pipeline run in
            milliseconds, from start to aggregation completion.
    """

    final_action: str = "allow"
    overall_risk_level: str = "low"
    detector_results: list[DetectionResult] = Field(default_factory=list)
    modifications: list[Modification] = Field(default_factory=list)
    pipeline_duration_ms: float = 0.0


@dataclass
class _TaskMeta:
    """Metadata tracked per asyncio.Task for result association."""

    detector_name: str
    message_index: int | None
    priority: int


class PipelineEngine:
    """Executes detectors in parallel with short-circuit cancellation.

    Args:
        short_circuit_on: When ``"block"`` (default), only ``block`` results
            trigger short-circuit. When ``"block_and_modify"``, ``modify``
            results also trigger short-circuit.
        flag_escalation: Optional compiled flag-escalation rule. When the
            aggregated ``final_action`` is ``"flag"`` and the rule evaluates
            to ``True``, ``final_action`` is upgraded to ``"block"``.
    """

    def __init__(
        self,
        short_circuit_on: str = "block",
        flag_escalation: FlagEscalationRule | None = None,
    ) -> None:
        if short_circuit_on not in ("block", "block_and_modify"):
            raise ValueError(
                f"short_circuit_on must be 'block' or 'block_and_modify', "
                f"got '{short_circuit_on}'"
            )
        self._short_circuit_on = short_circuit_on
        self._aggregator = ResultAggregator(flag_escalation=flag_escalation)

    async def run(
        self,
        detectors: list[Detector],
        contexts: list[DetectionContext],
        detector_configs: dict[str, dict[str, Any]],
    ) -> PipelineResult:
        """Run all detectors against all contexts in parallel.

        Args:
            detectors: List of initialized Detector instances.
            contexts: List of DetectionContext objects. The text content for
                each context is read from ``context.metadata["content"]``.
            detector_configs: Mapping of detector name to config dict. Each
                dict may contain: ``priority`` (int), ``on_error`` (str),
                ``block_threshold`` (float), ``flag_threshold`` (float),
                ``timeout_seconds`` (float | None), ``circuit_breaker``
                (CircuitBreaker | None).

        Returns:
            A :class:`PipelineResult` with aggregated outcomes.
        """
        start_time = time.monotonic()

        # If there are no detectors or no contexts, return immediately.
        if not detectors or not contexts:
            duration_ms = (time.monotonic() - start_time) * 1000.0
            return PipelineResult(
                final_action="allow",
                overall_risk_level="low",
                pipeline_duration_ms=duration_ms,
            )

        # Create tasks for all (context, detector) pairs.
        tasks: set[asyncio.Task[DetectionResult]] = set()
        task_meta: dict[asyncio.Task[DetectionResult], _TaskMeta] = {}

        # Results collected outside the task loop (e.g. circuit-breaker skips).
        early_results: list[DetectionResult] = []
        early_priorities: dict[str, int] = {}
        early_msg_indices: list[int | None] = []

        for ctx in contexts:
            content: str = ctx.metadata.get("content", "")

            for detector in detectors:
                det_name = detector.name
                cfg = detector_configs.get(det_name, {})

                priority: int = cfg.get("priority", _DEFAULT_PRIORITY)
                on_error: str = cfg.get("on_error", _DEFAULT_ON_ERROR)
                breaker: CircuitBreaker | None = cfg.get("circuit_breaker")

                # Circuit breaker check — if OPEN, skip the detector.
                if breaker is not None and not breaker.before_call():
                    fallback = breaker.fallback_action
                    result = self._make_fallback_result(
                        det_name, fallback, "Circuit breaker is open"
                    )
                    early_results.append(result)
                    early_priorities[det_name] = priority
                    early_msg_indices.append(ctx.message_index)
                    logger.warning(
                        "circuit_breaker_open_skipped",
                        detector=det_name,
                        fallback_action=fallback,
                    )
                    continue

                # Create the detection task.
                task = asyncio.create_task(
                    self._run_detector(
                        detector=detector,
                        content=content,
                        context=ctx,
                        config=cfg,
                        breaker=breaker,
                        on_error=on_error,
                    )
                )
                tasks.add(task)
                task_meta[task] = _TaskMeta(
                    detector_name=det_name,
                    message_index=ctx.message_index,
                    priority=priority,
                )

        # Monitor tasks with FIRST_COMPLETED until all done or short-circuit.
        collected_results: list[DetectionResult] = list(early_results)
        collected_priorities: dict[str, int] = dict(early_priorities)
        collected_msg_indices: list[int | None] = list(early_msg_indices)

        short_circuited = False

        while tasks and not short_circuited:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            tasks = pending  # remaining tasks

            for task in done:
                meta = task_meta[task]
                try:
                    result = task.result()
                except asyncio.CancelledError:
                    # Cancelled tasks are not collected.
                    continue

                collected_results.append(result)
                collected_priorities[meta.detector_name] = meta.priority
                collected_msg_indices.append(meta.message_index)

                if result.action == "block":
                    short_circuited = True
                    logger.info(
                        "pipeline_short_circuit",
                        detector=meta.detector_name,
                        action="block",
                    )
                elif (
                    result.action == "modify"
                    and self._short_circuit_on == "block_and_modify"
                ):
                    short_circuited = True
                    logger.info(
                        "pipeline_short_circuit",
                        detector=meta.detector_name,
                        action="modify",
                        mode="block_and_modify",
                    )

            # Cancel remaining tasks if short-circuited.
            if short_circuited and tasks:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks.clear()

        duration_ms = (time.monotonic() - start_time) * 1000.0

        # Aggregate all collected results.
        aggregated = self._aggregator.aggregate(
            collected_results,
            priorities=collected_priorities,
            message_indices=collected_msg_indices,
        )

        return PipelineResult(
            final_action=aggregated.final_action,
            overall_risk_level=aggregated.overall_risk_level,
            detector_results=collected_results,
            modifications=aggregated.modifications,
            pipeline_duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _run_detector(
        self,
        detector: Detector,
        content: str,
        context: DetectionContext,
        config: dict[str, Any],
        breaker: CircuitBreaker | None,
        on_error: str,
    ) -> DetectionResult:
        """Run a single detector with timeout, threshold decision, and error handling.

        This method is executed inside an asyncio.Task.
        """
        det_name = detector.name
        start = time.monotonic()

        try:
            timeout_seconds: float | None = config.get("timeout_seconds")

            if timeout_seconds is not None:
                result = await asyncio.wait_for(
                    detector.detect(content, context),
                    timeout=timeout_seconds,
                )
            else:
                result = await detector.detect(content, context)

            duration_ms = (time.monotonic() - start) * 1000.0
            result.duration_ms = duration_ms

            # Determine action via threshold engine (or keep "modify" if the
            # detector provided modified_content).
            if result.modified_content is not None:
                result.action = "modify"
            else:
                block_threshold: float = config.get(
                    "block_threshold", _DEFAULT_BLOCK_THRESHOLD
                )
                flag_threshold: float = config.get(
                    "flag_threshold", _DEFAULT_FLAG_THRESHOLD
                )
                result.action = ThresholdDecisionEngine.decide(
                    result.confidence,
                    block_threshold,
                    flag_threshold,
                )

            # Record success for circuit breaker.
            if breaker is not None:
                breaker.record_success()

            return result

        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000.0
            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "detector_timeout",
                detector=det_name,
                timeout_seconds=config.get("timeout_seconds"),
                duration_ms=duration_ms,
            )
            return self._make_error_result(
                det_name,
                on_error,
                f"Detector '{det_name}' timed out",
                duration_ms,
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000.0
            if breaker is not None:
                breaker.record_failure()
            logger.error(
                "detector_error",
                detector=det_name,
                error=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
            return self._make_error_result(
                det_name,
                on_error,
                str(exc),
                duration_ms,
            )

    @staticmethod
    def _make_error_result(
        detector_name: str,
        on_error: str,
        error_msg: str,
        duration_ms: float,
    ) -> DetectionResult:
        """Create a DetectionResult for a detector error or timeout.

        - ``fail_open`` → action="allow" (skip the detector, continue processing)
        - ``fail_closed`` → action="block" (block the request)
        """
        if on_error == "fail_closed":
            return DetectionResult(
                detector_name=detector_name,
                category="error",
                action="block",
                confidence=1.0,
                risk_level="high",
                message=f"Detector '{detector_name}' failed (fail_closed): {error_msg}",
                error=error_msg,
                duration_ms=duration_ms,
            )
        # fail_open (default)
        return DetectionResult(
            detector_name=detector_name,
            category="error",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message=f"Detector '{detector_name}' failed (fail_open): {error_msg}",
            error=error_msg,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _make_fallback_result(
        detector_name: str,
        fallback_action: str,
        reason: str,
    ) -> DetectionResult:
        """Create a DetectionResult for a circuit-breaker skip.

        - ``fail_open`` → action="allow" (skip the detector)
        - ``fail_closed`` → action="block" (block the request)
        """
        if fallback_action == "fail_closed":
            return DetectionResult(
                detector_name=detector_name,
                category="circuit_breaker",
                action="block",
                confidence=1.0,
                risk_level="high",
                message=f"Circuit breaker open for '{detector_name}' (fail_closed): {reason}",
                error=reason,
            )
        # fail_open (default)
        return DetectionResult(
            detector_name=detector_name,
            category="circuit_breaker",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message=f"Circuit breaker open for '{detector_name}' (fail_open): {reason}",
            error=reason,
        )
