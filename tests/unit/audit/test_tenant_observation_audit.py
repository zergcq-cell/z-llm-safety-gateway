"""Tenant observation projections into audit evidence."""

from __future__ import annotations

from z_llm_safety_gateway.audit.logger import AuditLogger
from z_llm_safety_gateway.audit.models import AuditEntry, DetectorLifecycleEvent
from z_llm_safety_gateway.tenancy.observation import (
    ObservationScope,
    TenantObservationContext,
)


def test_audit_entry_serializes_trusted_context_without_payload() -> None:
    """TC-TAU-001: Tenant attribution is additive and payload-free."""
    entry = AuditEntry(
        request_id="request-1",
        direction="input",
        tenant_context=TenantObservationContext(
            scope=ObservationScope.TENANT,
            tenant_id="acme",
            policy_id="strict-policy",
        ),
        content="secret-api-key",
    )

    line = entry.to_json_line()
    assert line["tenant_context"] == {
        "contract_version": "1.0",
        "scope": "tenant",
        "tenant_id": "acme",
        "policy_id": "strict-policy",
    }
    assert "secret-api-key" not in str(line["tenant_context"])
    assert AuditEntry(request_id="legacy", direction="input").to_json_line().get(
        "tenant_context"
    ) is None


def test_policy_lifecycle_event_cannot_claim_a_tenant() -> None:
    """TC-TAU-003: Shared policy lifecycle evidence has policy-only provenance."""
    event = DetectorLifecycleEvent(
        policy_id="strict-policy",
        detector_name="guard",
        direction="input",
        detector_type="builtin",
        old_state="initializing",
        new_state="unavailable",
        required=True,
        on_error="fail_closed",
        tenant_context=TenantObservationContext.policy("strict-policy"),
    )

    assert event.to_json_line()["tenant_context"] == {
        "contract_version": "1.0",
        "scope": "policy",
        "tenant_id": None,
        "policy_id": "strict-policy",
    }


def test_tenant_audit_projection_never_expands_content_retention() -> None:
    """TC-TAU-004: Attribution has a small fixed schema and no payload retention."""
    entry = AuditEntry(
        request_id="request-1",
        direction="output",
        tenant_context=TenantObservationContext(
            scope=ObservationScope.TENANT,
            tenant_id="a" * 64,
            policy_id="p" * 64,
        ),
        content="provider-key-should-not-be-projected",
    )

    context = entry.to_json_line()["tenant_context"]
    assert len(str(context).encode()) <= 512
    assert "content" not in context
    assert "provider-key" not in str(context)


def test_no_sink_marks_tenant_audit_evidence_unpersisted() -> None:
    """TC-TAU-005: Sink failure remains visible without changing safety action."""
    entry = AuditEntry(
        request_id="request-1",
        direction="input",
        tenant_context=TenantObservationContext.policy("strict-policy"),
        final_action="block",
    )
    logger = AuditLogger(file_enabled=False, stdout_enabled=False)

    logger.record(entry)

    assert entry.evidence_persisted is False
    assert entry.final_action == "block"


def test_disabled_audit_does_not_claim_persistence_failure() -> None:
    """TC-TAU-006: Disabled auditing is explicit and distinct from sink failure."""
    entry = AuditEntry(request_id="request-1", direction="input")

    AuditLogger(enabled=False, file_enabled=False, stdout_enabled=False).record(entry)

    assert entry.evidence_persisted is True
