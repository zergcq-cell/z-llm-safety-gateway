"""Flow evidence audit schema, privacy, and persistence failure tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from z_llm_safety_gateway.audit.logger import AuditLogger
from z_llm_safety_gateway.audit.models import AuditEntry
from z_llm_safety_gateway.audit.streaming_evidence import StreamingEvidenceAccumulator
from z_llm_safety_gateway.flow.evidence import (
    FlowEvidence,
    FlowStatus,
    NodeStatus,
    SafeEvidenceSummary,
    build_node_evidence,
)
from z_llm_safety_gateway.flow.policy import (
    AvailabilityPolicyConfig,
    NodePolicyConfig,
    PolicyDefaults,
    resolve_node_policy,
)
from z_llm_safety_gateway.observability import metrics
from z_llm_safety_gateway.routes.chat import _record_request_audit


def _evidence(*, status: NodeStatus = NodeStatus.SUCCEEDED) -> FlowEvidence:
    policy = resolve_node_policy(
        NodePolicyConfig(availability=AvailabilityPolicyConfig()),
        defaults=PolicyDefaults(),
    )
    node = build_node_evidence(
        contract_version="1.0",
        flow_id="input-flow",
        flow_version="1.0.0",
        execution_id="execution",
        node_id="node-b",
        definition_index=1,
        target_id="detector.guard",
        target_contract_version="1.0",
        target_implementation_version="1.0.0",
        effective_policy=policy,
        status=status,
        degraded=status is not NodeStatus.SUCCEEDED,
        reason_code=("completed" if status is NodeStatus.SUCCEEDED else "node_cancelled"),
        duration_ms=1.0,
        item_count=1,
        succeeded_items=1 if status is NodeStatus.SUCCEEDED else 0,
        failed_items=0,
        skipped_items=0,
        cancelled_items=1 if status is not NodeStatus.SUCCEEDED else 0,
        signals=("safety.allow",),
        optional_summary={
            "action": "allow",
            "raw_exception": "secret https://private-endpoint",
        },
    )
    first = node.model_copy(update={"node_id": "node-a", "definition_index": 0})
    return FlowEvidence(
        contract_version="1.0",
        execution_id="execution",
        flow_id="input-flow",
        flow_version="1.0.0",
        direction="input",
        stage="input",
        status=(FlowStatus.COMPLETED if status is NodeStatus.SUCCEEDED else FlowStatus.STOPPED),
        reason_code="completed" if status is NodeStatus.SUCCEEDED else "stop_signal",
        duration_ms=2.0,
        final_signals=("safety.allow",),
        nodes=(node, first),
    )


def test_tc_aud_701() -> None:
    """TC-AUD-701: additive audit fields link ordered Flow and Node evidence."""
    entry = AuditEntry(
        request_id="request",
        direction="input",
        final_action="allow",
        detectors=[],
    ).with_flow_evidence(_evidence())

    assert entry.request_id == "request"
    assert entry.final_action == "allow"
    assert entry.flow_id == "input-flow"
    assert entry.flow_version == "1.0.0"
    assert entry.flow_execution_id == "execution"
    assert entry.flow_status == "completed"
    assert [node.node_id for node in entry.node_evidence] == ["node-a", "node-b"]


def test_tc_aud_702() -> None:
    """TC-AUD-702: audit distinguishes actual policy, degradation, and cancellation."""
    entry = AuditEntry(request_id="request", direction="input").with_flow_evidence(
        _evidence(status=NodeStatus.CANCELLED)
    )
    serialized = entry.to_json_line()

    assert serialized["evidence_persisted"] is True
    assert serialized["node_evidence"][0]["status"] == "cancelled"
    assert serialized["node_evidence"][0]["degraded"] is True
    assert serialized["node_evidence"][0]["reason_code"] == "node_cancelled"
    assert (
        serialized["node_evidence"][0]["effective_policy"]["failure_action"]
        == "fail_open"
    )


def test_tc_aud_703(capsys: Any) -> None:
    """TC-AUD-703: evidence never stores payload even when content storage is enabled."""
    secret = "sk-123456789012345678901234567890"
    entry = AuditEntry(
        request_id="request",
        direction="input",
        content=secret,
    ).with_flow_evidence(_evidence())
    logger = AuditLogger(
        store_content=True,
        sanitize_logs=True,
        file_enabled=False,
        stdout_enabled=True,
    )

    logger.record(entry, flow_evidence=_evidence())
    payload = json.loads(capsys.readouterr().out)
    evidence_text = json.dumps(payload["node_evidence"])

    assert secret not in json.dumps(payload)
    assert "private-endpoint" not in evidence_text
    assert "raw_exception" not in evidence_text
    assert payload["content"] != secret


def test_tc_aud_704() -> None:
    """TC-AUD-704: streaming audit aggregates allow windows and keeps post-audit separate."""
    accumulator = StreamingEvidenceAccumulator()
    allow = _evidence()
    for index in range(1_000):
        accumulator.record_window(allow, window_index=index)
    post_audit = allow.model_copy(
        update={"execution_id": "post-audit", "stage": "post-audit"}
    )
    accumulator.set_post_audit(post_audit)
    summary = accumulator.summary()

    assert summary.execution_count == 1_000
    assert len(summary.buckets) == 2
    assert summary.buckets[0].execution_count == 1_000
    assert summary.post_audit == post_audit
    assert len(summary.model_dump_json().encode()) <= 256 * 1024


def test_tc_aud_705(caplog: Any) -> None:
    """TC-AUD-705: sink errors are nonblocking, explicit, stable, and metered."""

    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            del record
            raise RuntimeError("secret https://private-endpoint")

    logger = AuditLogger(file_enabled=False, stdout_enabled=False)
    logger._file_handler = FailingHandler()
    entry = AuditEntry(
        request_id="request",
        direction="input",
        final_action="block",
    )
    evidence = _evidence()
    metrics.set_enabled(True)
    try:
        with caplog.at_level(logging.WARNING):
            persisted = logger.record(entry, flow_evidence=evidence)
        rendered = metrics.generate_latest().decode()
    finally:
        metrics.set_enabled(False)

    assert persisted is not None
    assert persisted.evidence_persisted is False
    assert entry.final_action == "block"
    assert entry.evidence_persisted is False
    assert "safety_evidence_persistence_failures_total" in rendered
    assert "audit_evidence_persist_failed" in caplog.text
    assert "sink_error" in caplog.text
    assert "private-endpoint" not in caplog.text


def test_file_failure_is_reflected_in_later_stdout_record(capsys: Any) -> None:
    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            del record
            raise RuntimeError("private sink failure")

    logger = AuditLogger(file_enabled=False, stdout_enabled=True)
    logger._file_handler = FailingHandler()
    entry = AuditEntry(request_id="request", direction="input")

    logger.record(entry, flow_evidence=_evidence())

    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence_persisted"] is False


def test_request_retains_unpersisted_flow_evidence_after_sink_failure() -> None:
    """The production audit handoff updates request-held evidence truthfully."""
    evidence = _evidence()
    request = SimpleNamespace(state=SimpleNamespace(flow_evidence=[evidence]))
    entry = AuditEntry(request_id="request", direction="input").with_flow_evidence(
        evidence
    )
    logger = AuditLogger(file_enabled=False, stdout_enabled=False)

    persisted = _record_request_audit(request, logger, entry)

    assert persisted is not None
    assert persisted.evidence_persisted is False
    assert request.state.flow_evidence[0].evidence_persisted is False
    assert entry.attached_flow_evidence is persisted


def test_real_file_handler_write_failure_marks_evidence_unpersisted(
    tmp_path: Path,
) -> None:
    """A production handler must surface write failures that logging normally swallows."""

    class FailingStream:
        def write(self, value: str) -> int:
            del value
            raise OSError("disk full at private path")

        def flush(self) -> None:
            return None

    audit = AuditLogger(
        file_enabled=True,
        stdout_enabled=False,
        log_dir=str(tmp_path),
    )
    handler = audit._file_handler
    assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
    original_stream = handler.stream
    handler.stream = FailingStream()
    try:
        entry = AuditEntry(request_id="request", direction="input")
        persisted = audit.record(entry, flow_evidence=_evidence())
    finally:
        handler.stream = original_stream
        audit.close()

    assert persisted is not None
    assert persisted.evidence_persisted is False
    assert entry.evidence_persisted is False


def test_streaming_summary_reserves_budget_for_outer_envelope() -> None:
    """A legal near-limit post-audit cannot overflow its streaming wrapper."""
    base = _evidence()
    template = base.nodes[0]
    rule_ids = tuple(f"rule-{index}-" + "x" * 118 for index in range(16))
    nodes = []
    post_audit = base
    for index in range(256):
        node = template.model_copy(
            update={
                "definition_index": index,
                "node_id": f"post-audit-node-{index}",
                "evidence_summary": SafeEvidenceSummary(rule_ids=rule_ids),
            }
        )
        candidate = base.model_copy(update={"nodes": (*nodes, node)})
        if len(candidate.model_dump_json().encode()) > 256 * 1024:
            break
        nodes.append(node)
        post_audit = candidate

    signals: tuple[str, ...] = ()
    for signal_index in range(32):
        for signal_length in range(128, 0, -1):
            prefix = f"s{signal_index:02d}"
            signal = prefix + "x" * max(0, signal_length - len(prefix))
            candidate = post_audit.model_copy(
                update={"final_signals": (*signals, signal)}
            )
            if len(candidate.model_dump_json().encode()) <= 256 * 1024:
                signals = candidate.final_signals
                post_audit = candidate
                break

    assert len(post_audit.model_dump_json().encode()) > 256 * 1024 - 32
    accumulator = StreamingEvidenceAccumulator()
    accumulator.set_post_audit(post_audit)

    summary = accumulator.summary()

    assert len(summary.model_dump_json().encode()) <= 256 * 1024
    assert summary.post_audit is not None
    assert len(summary.post_audit.nodes) == len(post_audit.nodes)
