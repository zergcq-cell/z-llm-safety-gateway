"""Pipeline engine package — parallel detector execution and result aggregation.

Public API:

- :class:`ThresholdDecisionEngine` — maps confidence to action via thresholds
- :class:`FlagEscalationRule` — DSL parser for flag-to-block escalation
- :class:`ResultAggregator` — merges DetectionResults into a unified outcome
- :class:`PipelineEngine` — parallel execution with short-circuit cancellation
- :class:`PipelineResult` — the output model of ``PipelineEngine.run()``
"""

from __future__ import annotations

from z_llm_safety_gateway.pipeline.aggregator import AggregatedResult, ResultAggregator
from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule
from z_llm_safety_gateway.pipeline.threshold import ThresholdDecisionEngine

__all__ = [
    "AggregatedResult",
    "FlagEscalationRule",
    "PipelineEngine",
    "PipelineResult",
    "ResultAggregator",
    "ThresholdDecisionEngine",
]
