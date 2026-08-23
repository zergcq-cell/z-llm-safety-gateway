"""Bounded Flow metrics and trace hierarchy tests."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from tests.unit.audit.test_flow_evidence import _evidence
from z_llm_safety_gateway.flow.evidence import FlowEvidence, FlowStatus, NodeStatus
from z_llm_safety_gateway.observability import metrics, tracing
from z_llm_safety_gateway.observability.flow import (
    observe_flow_evidence,
    sanitize_observable_value,
    trace_flow_evidence,
)


def test_tc_obs_701() -> None:
    """TC-OBS-701: Flow and Node metrics use bounded identity and terminal labels."""
    evidence = _evidence(status=NodeStatus.CANCELLED)
    metrics.set_enabled(True)
    try:
        observe_flow_evidence(evidence)
        output = metrics.generate_latest().decode()
    finally:
        metrics.set_enabled(False)

    assert (
        'safety_flow_executions_total{direction="input",flow_id="input-flow",'
        'status="stopped"}' in output
    )
    assert (
        'node_id="node-a",reason_code="node_cancelled",status="cancelled"'
        in output
    )
    assert "target_implementation_version" not in output
    assert "request_id" not in output


def test_tc_obs_702() -> None:
    """TC-OBS-702: disabled Flow metrics are allocation-safe no-ops."""
    evidence = _evidence()
    metrics.set_enabled(False)

    assert observe_flow_evidence(evidence) is evidence
    assert metrics.generate_latest() == b""


def test_tc_obs_703(monkeypatch: Any) -> None:
    """TC-OBS-703: request→flow→node→nested-flow spans preserve real statuses."""
    events: list[tuple[str, int, dict[str, Any]]] = []

    class Span(AbstractContextManager[Any]):
        depth = 0

        def __init__(self, name: str, attributes: dict[str, Any]) -> None:
            self.name = name
            self.attributes = attributes

        def __enter__(self) -> Span:
            events.append((self.name, Span.depth, self.attributes))
            Span.depth += 1
            return self

        def __exit__(self, *args: Any) -> None:
            Span.depth -= 1

    class Tracer:
        def start_as_current_span(self, name: str, attributes: Any = None) -> Span:
            return Span(name, attributes or {})

    monkeypatch.setattr(tracing, "get_tracer", lambda: Tracer())
    secret_version = "https://internal.example/token=super-secret"
    parent = _evidence(status=NodeStatus.CANCELLED)
    parent = parent.model_copy(
        update={
            "nodes": (
                parent.nodes[0].model_copy(
                    update={
                        "child_execution_id": "child",
                        "target_implementation_version": secret_version,
                    }
                ),
                *parent.nodes[1:],
            )
        }
    )
    child = FlowEvidence(
        contract_version="1.0",
        execution_id="child",
        parent_execution_id=parent.execution_id,
        flow_id="child-flow",
        flow_version="1.0.0",
        direction="input",
        stage="nested-flow",
        status=FlowStatus.TIMED_OUT,
        reason_code="flow_timeout",
        duration_ms=1.0,
    )

    with (
        tracing.trace_request("request-super-secret", "model", "input"),
        trace_flow_evidence(parent, children=(child,)),
    ):
        pass

    assert events[0][0] == "gateway.request"
    assert any(name == "flow.input-flow" and depth == 1 for name, depth, _ in events)
    assert any(name == "node.node-a" and depth == 2 for name, depth, _ in events)
    assert any(name == "flow.child-flow" and depth == 3 for name, depth, _ in events)
    attributes = " ".join(str(item[2]) for item in events)
    assert "cancelled" in attributes
    assert "flow_timeout" in attributes
    assert "content" not in attributes
    assert "user_id" not in attributes
    assert "request-super-secret" not in attributes
    assert secret_version not in attributes
    assert "node.target_version_hash" in attributes


def test_tc_obs_704() -> None:
    """TC-OBS-704: malicious dynamic values are rejected with a metric signal."""
    metrics.set_enabled(True)
    try:
        value, sanitized = sanitize_observable_value(
            "node_id", "secret https://endpoint/" + "x" * 300
        )
        output = metrics.generate_latest().decode()
    finally:
        metrics.set_enabled(False)

    assert value == "invalid"
    assert sanitized is True
    assert (
        'safety_observability_sanitizations_total{field="node_id",'
        'reason="invalid_value"}' in output
    )
    assert "endpoint" not in output
