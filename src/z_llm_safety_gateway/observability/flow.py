"""Privacy-bounded metrics and trace projection for Flow evidence."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager

from z_llm_safety_gateway.flow.evidence import FlowEvidence
from z_llm_safety_gateway.observability import metrics, tracing
from z_llm_safety_gateway.observability.tenant import tenant_trace_fields
from z_llm_safety_gateway.tenancy.observation import TenantObservationContext

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ENUM_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def sanitize_observable_value(field: str, value: str) -> tuple[str, bool]:
    """Accept validated config IDs/enums only; reject rather than truncate payloads."""
    pattern = _REASON_PATTERN if field == "reason_code" else _ENUM_PATTERN
    if field in {"flow_id", "node_id", "target_id"}:
        pattern = _ID_PATTERN
    if pattern.fullmatch(value):
        return value, False
    metrics.record_observability_sanitization(field, "invalid_value")
    return "invalid", True


def _hash_observable_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def observe_flow_evidence(
    evidence: FlowEvidence,
    *,
    children: tuple[FlowEvidence, ...] = (),
    tenant_context: TenantObservationContext | None = None,
) -> FlowEvidence:
    """Project immutable evidence to no-op-safe metrics and optional traces."""
    if not metrics.is_enabled() and not tracing.is_enabled():
        return evidence
    flow_id, _ = sanitize_observable_value("flow_id", evidence.flow_id)
    direction, _ = sanitize_observable_value("direction", evidence.direction)
    status, _ = sanitize_observable_value("status", evidence.status.value)
    metrics.record_flow_execution(
        flow_id,
        direction,
        status,
        evidence.duration_ms / 1000.0,
    )
    for node in evidence.nodes:
        node_id, _ = sanitize_observable_value("node_id", node.node_id)
        node_status, _ = sanitize_observable_value("status", node.status.value)
        reason, _ = sanitize_observable_value("reason_code", node.reason_code)
        metrics.record_flow_node(
            flow_id,
            direction,
            node_id,
            node_status,
            reason,
        )
    if tracing.is_enabled():
        with trace_flow_evidence(
            evidence, children=children, tenant_context=tenant_context
        ):
            pass
    return evidence


@contextmanager
def trace_flow_evidence(
    evidence: FlowEvidence,
    *,
    children: tuple[FlowEvidence, ...] = (),
    tenant_context: TenantObservationContext | None = None,
) -> Iterator[None]:
    """Emit flow→node→nested-flow spans using evidence-only safe attributes."""
    tracer = tracing.get_tracer()
    child_by_execution = {child.execution_id: child for child in children}
    flow_id, _ = sanitize_observable_value("flow_id", evidence.flow_id)
    attributes = {
        "flow.id": flow_id,
        "flow.version": evidence.flow_version,
        "flow.status": evidence.status.value,
        "flow.reason_code": evidence.reason_code,
        "flow.direction": evidence.direction,
    }
    attributes.update(tenant_trace_fields(tenant_context))
    with tracer.start_as_current_span(
        f"flow.{flow_id}",
        attributes=attributes,
    ):
        for node in evidence.nodes:
            node_id, _ = sanitize_observable_value("node_id", node.node_id)
            target_id, _ = sanitize_observable_value("target_id", node.target_id)
            with tracer.start_as_current_span(
                f"node.{node_id}",
                attributes={
                    "node.id": node_id,
                    "node.target_id": target_id,
                    "node.target_version_hash": _hash_observable_value(
                        node.target_implementation_version
                    ),
                    "node.status": node.status.value,
                    "node.reason_code": node.reason_code,
                    "node.degraded": node.degraded,
                },
            ):
                child = (
                    child_by_execution.get(node.child_execution_id)
                    if node.child_execution_id is not None
                    else None
                )
                if child is not None:
                    with trace_flow_evidence(
                        child, children=children, tenant_context=tenant_context
                    ):
                        pass
        yield
