"""Core Flow and Node evidence chain tests."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.audit.streaming_evidence import StreamingEvidenceAccumulator
from z_llm_safety_gateway.flow.evidence import (
    DEFAULT_MAX_EVIDENCE_SIZE,
    FlowEvidence,
    FlowStatus,
    NodeStatus,
    bound_flow_evidence,
    build_node_evidence,
)
from z_llm_safety_gateway.flow.policy import NodePolicyConfig, PolicyDefaults, resolve_node_policy


def _policy() -> Any:
    return resolve_node_policy(NodePolicyConfig(), defaults=PolicyDefaults())


def _node(**overrides: Any) -> Any:
    values: dict[str, Any] = {
        "contract_version": "1.0",
        "flow_id": "input-flow",
        "flow_version": "1.0.0",
        "execution_id": "flow-exec-1",
        "node_id": "detector-node",
        "definition_index": 0,
        "target_id": "detector.test",
        "target_contract_version": "1.0",
        "target_implementation_version": "plugin-build-7",
        "effective_policy": _policy(),
        "status": NodeStatus.SUCCEEDED,
        "degraded": False,
        "reason_code": "completed",
        "duration_ms": 1.25,
        "item_count": 1,
        "succeeded_items": 1,
        "failed_items": 0,
        "skipped_items": 0,
        "cancelled_items": 0,
        "signals": ("safety.allow",),
    }
    values.update(overrides)
    return build_node_evidence(**values)


def test_tc_nec_001() -> None:
    """TC-NEC-001: core evidence identifies contracts, policy, result, and timing."""
    node = _node()
    flow = FlowEvidence(
        contract_version="1.0",
        execution_id="flow-exec-1",
        parent_execution_id=None,
        flow_id="input-flow",
        flow_version="1.0.0",
        direction="input",
        stage="input",
        status=FlowStatus.COMPLETED,
        reason_code="completed",
        duration_ms=1.5,
        final_signals=("safety.allow",),
        nodes=(node,),
    )

    assert node.node_id == "detector-node"
    assert node.target_id == "detector.test"
    assert node.target_contract_version == "1.0"
    assert node.target_implementation_version == "plugin-build-7"
    assert node.effective_policy.sources.timeout == "default"
    assert node.duration_ms == 1.25
    assert flow.execution_id == "flow-exec-1"
    assert flow.stage == "input"
    assert flow.status == FlowStatus.COMPLETED
    assert flow.final_signals == ("safety.allow",)


def test_tc_nec_002() -> None:
    """TC-NEC-002: evidence order follows definitions and nested executions retain parents."""
    parent_execution_id = "parent-execution"
    unordered = (
        _node(node_id="third", definition_index=2),
        _node(
            node_id="nested",
            definition_index=0,
            child_execution_id="child-execution",
        ),
        _node(node_id="second", definition_index=1),
    )
    first = FlowEvidence(
        contract_version="1.0",
        execution_id=parent_execution_id,
        flow_id="parent-flow",
        flow_version="1.0.0",
        direction="output",
        stage="sync-output",
        status="completed",
        reason_code="completed",
        duration_ms=2.0,
        final_signals=("safety.allow",),
        nodes=unordered,
    )
    second = FlowEvidence.model_validate(first.model_dump())
    child = FlowEvidence(
        contract_version="1.0",
        execution_id="child-execution",
        parent_execution_id=parent_execution_id,
        flow_id="child-flow",
        flow_version="1.0.0",
        direction="output",
        stage="nested-flow",
        status="completed",
        reason_code="completed",
        duration_ms=1.0,
        final_signals=("safety.allow",),
        nodes=(),
    )

    assert [node.node_id for node in first.nodes] == ["nested", "second", "third"]
    assert [node.node_id for node in second.nodes] == ["nested", "second", "third"]
    assert first.nodes[0].child_execution_id == child.execution_id
    assert child.parent_execution_id == first.execution_id


@pytest.mark.parametrize(
    ("status", "counts"),
    [
        (NodeStatus.SUCCEEDED, (1, 0, 0, 0)),
        (NodeStatus.FAILED, (0, 1, 0, 0)),
        (NodeStatus.TIMED_OUT, (0, 1, 0, 0)),
        (NodeStatus.SKIPPED, (0, 0, 1, 0)),
        (NodeStatus.CANCELLED, (0, 0, 0, 1)),
        (NodeStatus.PARTIAL, (1, 1, 0, 0)),
    ],
)
def test_tc_nec_003(status: NodeStatus, counts: tuple[int, int, int, int]) -> None:
    """TC-NEC-003: every terminal or partial state has reconcilable evidence."""
    succeeded, failed, skipped, cancelled = counts
    reason = "completed" if status is NodeStatus.SUCCEEDED else f"node_{status.value}"
    node = _node(
        status=status,
        degraded=status is not NodeStatus.SUCCEEDED,
        reason_code=reason,
        item_count=sum(counts),
        succeeded_items=succeeded,
        failed_items=failed,
        skipped_items=skipped,
        cancelled_items=cancelled,
    )

    assert node.status is status
    assert node.terminal_item_count == node.item_count
    if status is not NodeStatus.SUCCEEDED:
        assert node.reason_code

    with pytest.raises(ValidationError):
        _node(status=status, item_count=2, succeeded_items=1, failed_items=0)


def test_tc_nec_004() -> None:
    """TC-NEC-004: core evidence rejects raw content, details, endpoints, and exceptions."""
    raw = "customer secret prompt"
    modified = "modified private completion"
    endpoint = "http://internal-detector:50051"
    exception = "RuntimeError(token=super-secret)"
    content_hash = hashlib.sha256(raw.encode()).hexdigest()

    node = _node(
        status=NodeStatus.FAILED,
        degraded=True,
        reason_code="capability_error",
        succeeded_items=0,
        failed_items=1,
        signals=("safety.block",),
        optional_summary={
            "content_hash": content_hash,
            "content_length": len(raw),
            "content": raw,
            "modified_content": modified,
            "message": endpoint,
            "exception": exception,
        },
    )
    serialized = node.model_dump_json()

    assert content_hash in serialized
    assert str(len(raw)) in serialized
    for forbidden in (raw, modified, endpoint, exception, "modified_content"):
        assert forbidden not in serialized
    assert node.details_truncated is True
    assert node.evidence_rejected_reason == "invalid_evidence_summary"

    with pytest.raises(ValidationError):
        _node(reason_code=exception)


def test_tc_nec_005() -> None:
    """TC-NEC-005: optional evidence is signalled and trimmed before core evidence."""
    node = _node(
        signals=tuple(f"signal.{index}" for index in range(80)),
        optional_summary={"rule_ids": tuple(f"rule-{index}" for index in range(100))},
        max_evidence_size=2048,
    )

    assert node.node_id == "detector-node"
    assert node.status is NodeStatus.SUCCEEDED
    assert len(node.signals) <= 32
    assert node.details_truncated is True
    assert node.evidence_rejected_reason in {
        "invalid_evidence_summary",
        "signal_limit_exceeded",
        "evidence_budget_exceeded",
    }
    assert len(node.model_dump_json().encode()) <= 2048


def test_complete_flow_evidence_is_bounded_at_maximum_graph_size() -> None:
    nodes = tuple(
        _node(
            node_id=f"node-{index}",
            definition_index=index,
            signals=tuple(f"signal.{signal}" for signal in range(32)),
        )
        for index in range(256)
    )
    evidence = FlowEvidence(
        contract_version="1.0",
        execution_id="execution",
        flow_id="maximum-flow",
        flow_version="1.0.0",
        direction="input",
        stage="input",
        status=FlowStatus.COMPLETED,
        reason_code="completed",
        duration_ms=1.0,
        final_signals=tuple(f"signal.{signal}" for signal in range(32)),
        nodes=nodes,
    )

    bounded = bound_flow_evidence(evidence)

    assert len(bounded.nodes) == 256
    assert bounded.details_truncated is True
    assert all(node.details_truncated for node in bounded.nodes)
    assert len(bounded.model_dump_json().encode()) <= DEFAULT_MAX_EVIDENCE_SIZE


def test_maximum_policy_evidence_is_bounded_without_losing_node_decisions() -> None:
    """Maximum legal stop policies retain every terminal decision under 256 KiB."""
    nodes = []
    original_stop_signals: list[tuple[str, ...]] = []
    for node_index in range(256):
        stop_signals = tuple(
            (
                f"signal.{node_index:03d}.{signal_index:02d}."
                + "x" * 128
            )[:128]
            for signal_index in range(32)
        )
        policy = resolve_node_policy(
            NodePolicyConfig(
                stop={"signals": stop_signals},
            ),
            defaults=PolicyDefaults(),
        )
        original_stop_signals.append(stop_signals)
        nodes.append(
            _node(
                node_id=f"node-{node_index}",
                definition_index=node_index,
                effective_policy=policy,
                status=NodeStatus.FAILED,
                degraded=True,
                reason_code="capability_error",
                succeeded_items=0,
                failed_items=1,
                signals=tuple(f"signal.{index}" for index in range(32)),
            )
        )
    evidence = FlowEvidence(
        contract_version="1.0",
        execution_id="maximum-policy-execution",
        flow_id="maximum-policy-flow",
        flow_version="1.0.0",
        direction="input",
        stage="input",
        status=FlowStatus.FAILED,
        reason_code="capability_error",
        duration_ms=1.0,
        final_signals=tuple(f"signal.{index}" for index in range(32)),
        nodes=tuple(nodes),
    )

    bounded = bound_flow_evidence(evidence)
    repeated = bound_flow_evidence(evidence)

    assert len(bounded.model_dump_json().encode()) <= DEFAULT_MAX_EVIDENCE_SIZE
    assert len(bounded.nodes) == 256
    assert [node.status for node in bounded.nodes] == [NodeStatus.FAILED] * 256
    assert [node.reason_code for node in bounded.nodes] == [
        "capability_error"
    ] * 256
    assert all(
        node.effective_policy.timeout == original.effective_policy.timeout
        and node.effective_policy.failure == original.effective_policy.failure
        and node.effective_policy.availability
        == original.effective_policy.availability
        and node.effective_policy.degradation
        == original.effective_policy.degradation
        and node.effective_policy.sources == original.effective_policy.sources
        for node, original in zip(bounded.nodes, evidence.nodes, strict=True)
    )
    compact_stop_signals = [
        node.effective_policy.stop.signals for node in bounded.nodes
    ]
    assert compact_stop_signals == [
        node.effective_policy.stop.signals for node in repeated.nodes
    ]
    assert len(set(compact_stop_signals)) == 256
    assert all(
        len(signals) == 1
        and signals[0].startswith("h:")
        and len(signals[0]) == 26
        for signals in compact_stop_signals
    )
    serialized = bounded.model_dump_json()
    assert all(signals[0] not in serialized for signals in original_stop_signals)


def test_tc_nec_006() -> None:
    """TC-NEC-006: every window produces evidence before bounded aggregation."""
    accumulator = StreamingEvidenceAccumulator()
    for index in range(80):
        flow = FlowEvidence(
            contract_version="1.0",
            execution_id=f"window-{index}",
            flow_id="output-flow",
            flow_version="1.0.0",
            direction="output",
            stage="sliding-window",
            status=FlowStatus.COMPLETED,
            reason_code="completed",
            duration_ms=1.0,
            final_signals=("safety.allow",),
            nodes=(_node(),),
        )
        accumulator.record_window(flow, window_index=index)
    trigger = flow.model_copy(
        update={
            "execution_id": "window-trigger",
            "final_signals": ("safety.block",),
            "reason_code": "stop_signal",
        }
    )
    accumulator.record_window(trigger, window_index=80)
    summary = accumulator.summary()

    assert summary.execution_count == 81
    assert sum(bucket.execution_count for bucket in summary.buckets) >= 81
    assert any(bucket.trigger_window_indices == (80,) for bucket in summary.buckets)
    assert len(summary.model_dump_json().encode()) <= 256 * 1024


def test_tc_nec_007() -> None:
    """TC-NEC-007: sink failure returns intact core evidence marked unpersisted."""
    from z_llm_safety_gateway.audit.logger import AuditLogger
    from z_llm_safety_gateway.audit.models import AuditEntry

    class FailingHandler:
        def emit(self, record: object) -> None:
            del record
            raise OSError("secret-write-failure")

    flow = FlowEvidence(
        contract_version="1.0",
        execution_id="flow-exec-1",
        flow_id="input-flow",
        flow_version="1.0.0",
        direction="input",
        stage="input",
        status=FlowStatus.COMPLETED,
        reason_code="completed",
        duration_ms=1.0,
        nodes=(_node(),),
    )
    logger = AuditLogger(file_enabled=False, stdout_enabled=False)
    logger._file_handler = FailingHandler()  # type: ignore[assignment]
    persisted = logger.record(
        AuditEntry(request_id="request", direction="input"),
        flow_evidence=flow,
    )

    assert persisted is not None
    assert persisted.evidence_persisted is False
    assert persisted.nodes == flow.nodes
    assert flow.evidence_persisted is True
