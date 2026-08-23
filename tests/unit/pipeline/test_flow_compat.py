"""PipelineEngine public compatibility while delegating to Flow Runtime."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

import pytest
import structlog

from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.flow.contracts import (
    CapabilityNodeDefinition,
    FlowDefinition,
    FlowNodeDefinition,
)
from z_llm_safety_gateway.flow.evidence import FlowStatus, NodeStatus
from z_llm_safety_gateway.flow.policy import (
    NodePolicyConfig,
    PolicyDefaults,
    resolve_node_policy,
)
from z_llm_safety_gateway.flow.runtime import FlowRuntime
from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.observability import metrics, tracing
from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult


class DetectorStub:
    name = "stub"
    category = "test"
    description = "stub"
    version = "1"

    def __init__(self) -> None:
        self.calls = 0

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        del content, context
        self.calls += 1
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.9,
            risk_level="high",
            message="result",
        )


async def test_tc_pe_001() -> None:
    """TC-PE-001: constructor/run/PipelineResult and legacy semantics remain available."""
    detector = DetectorStub()
    context = DetectionContext(
        direction="input",
        request_id="request",
        message_index=2,
        metadata={"content": "hello"},
    )
    engine = PipelineEngine(short_circuit_on="block")
    result = await engine.run(
        [detector],
        [context],
        {
            detector.name: {
                "priority": 10,
                "block_threshold": 0.8,
                "flag_threshold": 0.5,
                "on_error": "fail_open",
            }
        },
    )

    assert isinstance(result, PipelineResult)
    assert result.final_action == "block"
    assert result.overall_risk_level == "high"
    assert detector.calls == 1

    empty = await engine.run([], [], {})
    assert empty.final_action == "allow"
    assert empty.detector_results == []

    with pytest.raises(ValueError):
        PipelineEngine(short_circuit_on="invalid")


async def test_tc_pe_002(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-PE-002: facade invokes each detector once through one FlowRuntime execution."""
    calls = 0
    original_execute = FlowRuntime.execute

    async def counted_execute(self: FlowRuntime, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return await original_execute(self, *args, **kwargs)

    monkeypatch.setattr(FlowRuntime, "execute", counted_execute)
    detector = DetectorStub()
    result = await PipelineEngine().run(
        [detector],
        [
            DetectionContext(
                direction="input",
                request_id="request",
                metadata={"content": "hello"},
            )
        ],
        {detector.name: {"block_threshold": 1.0, "flag_threshold": 1.0}},
    )

    assert calls == 1
    assert detector.calls == 1
    assert result.pipeline_duration_ms >= 0


async def test_nested_stopped_flow_preserves_child_block_result_and_partial_evidence() -> None:
    """A child stop is a converged result, while the parent Node remains partial."""
    child_node = CapabilityNodeDefinition(
        contract_version="1.0",
        node_id="guard",
        capability_id="detector.stub",
        input_schema="safety.text.v1",
        output_schema="safety.detector-result.v1",
    )
    child = FlowDefinition(
        contract_version="1.0",
        flow_id="child-flow",
        version="1.0.0",
        input_schema="safety.text.v1",
        output_schema="safety.detector-result.v1",
        nodes=(child_node,),
        reducer_capability_id="detector-result-reducer",
    )
    parent_node = FlowNodeDefinition(
        contract_version="1.0",
        node_id="nested-guard",
        flow_id=child.flow_id,
        flow_version=child.version,
        input_schema=child.input_schema,
        output_schema=child.output_schema,
    )
    parent = FlowDefinition(
        contract_version="1.0",
        flow_id="parent-flow",
        version="1.0.0",
        input_schema="safety.text.v1",
        output_schema="safety.detector-result.v1",
        nodes=(parent_node,),
        reducer_capability_id="detector-result-reducer",
    )
    policy = resolve_node_policy(NodePolicyConfig(), defaults=PolicyDefaults())
    engine = PipelineEngine(
        flows=(parent, child),
        input_flow=(parent.flow_id, parent.version),
        resolved_policies={
            (parent.flow_id, parent.version, parent_node.node_id): policy,
            (child.flow_id, child.version, child_node.node_id): policy,
        },
    )
    detector = DetectorStub()

    result = await engine.run(
        [detector],
        [
            DetectionContext(
                direction="input",
                request_id="nested-request",
                metadata={"content": "hello"},
            )
        ],
        {
            detector.name: {
                "block_threshold": 0.8,
                "flag_threshold": 0.5,
                "on_error": "fail_open",
            }
        },
    )

    assert result.final_action == "block"
    assert [item.detector_name for item in result.detector_results] == [detector.name]
    assert result.flow_evidence is not None
    assert result.flow_evidence.status is FlowStatus.STOPPED
    assert result.flow_evidence.nodes[0].status is NodeStatus.PARTIAL
    assert result.flow_evidence.nodes[0].item_count == 1
    assert result.flow_evidence.nodes[0].failed_items == 1


async def test_tc_pe_003() -> None:
    """TC-PE-003: Flow facade meets latency/throughput bounds and leaks no tasks."""
    previous_metrics_enabled = metrics.is_enabled()
    previous_structlog_config = structlog.get_config()
    detectors: list[Any] = []
    try:
        metrics.set_enabled(False)
        assert not metrics.is_enabled()
        assert not tracing.is_enabled()
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        )
        try:
            registry = create_default_registry()
            detector_names = ("prompt_injection", "secret_leak", "sensitive_words")
            detectors = [registry.get(name)() for name in detector_names]
            configs = {
                name: {
                    "priority": 1,
                    "on_error": "fail_open",
                    "timeout_seconds": 5.0,
                    "words": ["urgent money transfer"],
                    "count_block_threshold": 2,
                }
                for name in detector_names
            }
            for detector in detectors:
                await detector.initialize(configs[detector.name])

            engine = PipelineEngine()
            context = DetectionContext(
                direction="input",
                request_id="benchmark",
                metadata={"content": "Explain the water cycle for a school project."},
            )
            for _ in range(50):
                await engine.run(detectors, [context], configs)

            latencies: list[float] = []
            throughput_trials: list[float] = []
            for _ in range(5):
                trial_started = time.perf_counter()
                for _ in range(750):
                    request_started = time.perf_counter()
                    await engine.run(detectors, [context], configs)
                    latencies.append(time.perf_counter() - request_started)
                elapsed = time.perf_counter() - trial_started
                throughput_trials.append(750 / elapsed)
        finally:
            structlog.configure(**previous_structlog_config)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99) - 1]
        # Use best-of-five for this sub-second in-process capacity check so an
        # unrelated scheduler pause cannot turn host contention into a product
        # regression. P99 still includes every recorded request latency.
        throughput = max(throughput_trials)

        assert p99 < 0.200
        # Coverage tracing intentionally instruments every executed line and makes
        # a microbenchmark incomparable with the uninstrumented release baseline.
        if sys.gettrace() is None:
            assert throughput >= 7_128
        assert engine.pending_flow_task_count == 0
    finally:
        for detector in reversed(detectors):
            shutdown = getattr(detector, "shutdown", None)
            if callable(shutdown):
                await shutdown()
        metrics.set_enabled(previous_metrics_enabled)


async def test_pipeline_plan_cache_invalidates_for_mutated_config() -> None:
    """The compatibility facade must honor a caller's in-place config changes."""
    detector = DetectorStub()
    context = DetectionContext(
        direction="input",
        request_id="request",
        metadata={"content": "hello"},
    )
    configs = {detector.name: {"block_threshold": 1.0, "flag_threshold": 1.0}}
    engine = PipelineEngine()

    first = await engine.run([detector], [context], configs)
    configs[detector.name]["block_threshold"] = 0.8
    second = await engine.run([detector], [context], configs)

    assert first.final_action == "allow"
    assert second.final_action == "block"
