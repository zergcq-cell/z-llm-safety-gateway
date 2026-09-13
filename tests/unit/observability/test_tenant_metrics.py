"""Bounded tenant observability metric tests."""

from __future__ import annotations

from types import SimpleNamespace

from z_llm_safety_gateway.audit.models import AuditEntry
from z_llm_safety_gateway.observability import metrics
from z_llm_safety_gateway.routes.chat import _record_request_audit
from z_llm_safety_gateway.tenancy.observation import (
    ObservationScope,
    TenantObservationContext,
)


def test_tenant_decisions_use_only_allowlisted_tenant_ids() -> None:
    """TC-TME-001/004: Tenant detail is bounded and policy IDs never become labels."""
    metrics.set_enabled(True, metric_tenant_ids=("acme",))
    try:
        metrics.record_tenant_decision(
            TenantObservationContext(ObservationScope.TENANT, "acme", "strict"),
            direction="input",
            action="block",
        )
        metrics.record_tenant_decision(
            TenantObservationContext(ObservationScope.TENANT, "globex", "strict"),
            direction="output",
            action="allow",
        )
        output = metrics.generate_latest().decode()
    finally:
        metrics.set_enabled(False)

    assert 'tenant_id="acme",tenant_scope="tenant"' in output
    assert 'tenant_id="other",tenant_scope="tenant_other"' in output
    assert "strict" not in output


def test_tenant_metric_events_are_finite_and_disabled_is_noop() -> None:
    """TC-TME-003/005: Event names and registries do not grow from request input."""
    metrics.set_enabled(False)
    metrics.record_tenant_event(
        TenantObservationContext.unattributed(), "attacker-controlled-event"
    )
    assert metrics.generate_latest() == b""

    metrics.set_enabled(True, metric_tenant_ids=())
    try:
        metrics.record_tenant_event(
            TenantObservationContext.unattributed(), "attacker-controlled-event"
        )
        output = metrics.generate_latest().decode()
    finally:
        metrics.set_enabled(False)

    assert 'event="projection_sanitized"' in output
    assert "attacker-controlled-event" not in output


def test_tenant_metrics_are_isolated_per_application_runtime() -> None:
    """TC-TME-005: one app's allowlist never changes another app's labels."""
    acme_app = metrics.create_runtime(True, metric_tenant_ids=("acme",))
    globex_app = metrics.create_runtime(True, metric_tenant_ids=("globex",))
    context = TenantObservationContext(ObservationScope.TENANT, "acme", "strict")

    metrics.record_tenant_decision(
        context, direction="input", action="allow", runtime=acme_app
    )
    metrics.record_tenant_decision(
        context, direction="input", action="allow", runtime=globex_app
    )

    assert 'tenant_id="acme",tenant_scope="tenant"' in acme_app.generate().decode()
    assert 'tenant_id="other",tenant_scope="tenant_other"' in globex_app.generate().decode()


def test_tenant_decision_is_not_recounted_when_audit_is_retried() -> None:
    """TC-TME-002: one final request direction contributes exactly one count."""
    runtime = metrics.create_runtime(True, metric_tenant_ids=("acme",))
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant_observation_context=TenantObservationContext(
                ObservationScope.TENANT, "acme", "strict"
            )
        ),
        app=SimpleNamespace(state=SimpleNamespace(metrics_runtime=runtime)),
    )
    entry = AuditEntry(request_id="request-1", direction="input", final_action="block")
    logger = SimpleNamespace(record=lambda value: None)

    _record_request_audit(request, logger, entry)
    _record_request_audit(request, logger, entry)

    output = runtime.generate().decode()
    assert 'tenant_id="acme",tenant_scope="tenant"' in output
    assert (
        'safety_tenant_decisions_total{action="block",direction="input",'
        'tenant_id="acme",tenant_scope="tenant"} 1.0'
    ) in output
