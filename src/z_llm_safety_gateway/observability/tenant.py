"""Safe, task-local structured-log projection for tenant observations."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager

import structlog

from z_llm_safety_gateway.tenancy.observation import TenantObservationContext

_OBSERVATION_ID = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")


def tenant_log_fields(
    context: TenantObservationContext | None,
) -> dict[str, str]:
    """Return only the fixed, trusted keys permitted in gateway logs."""
    if context is None:
        return {}
    fields = {"tenant_scope": context.scope.value}
    if context.tenant_id is not None and _OBSERVATION_ID.fullmatch(context.tenant_id):
        fields["tenant_id"] = context.tenant_id
    if context.policy_id is not None and _OBSERVATION_ID.fullmatch(context.policy_id):
        fields["tenant_policy_id"] = context.policy_id
    return fields


def tenant_trace_fields(context: TenantObservationContext | None) -> dict[str, str]:
    """Return the corresponding safe OpenTelemetry attribute projection."""
    log_fields = tenant_log_fields(context)
    fields = {"tenant.scope": log_fields["tenant_scope"]} if log_fields else {}
    if "tenant_id" in log_fields:
        fields["tenant.id"] = log_fields["tenant_id"]
    if "tenant_policy_id" in log_fields:
        fields["tenant.policy_id"] = log_fields["tenant_policy_id"]
    return fields


@contextmanager
def bound_tenant_observation(
    context: TenantObservationContext | None,
) -> Iterator[None]:
    """Bind trusted fields for this task and always restore prior context."""
    tokens = structlog.contextvars.bind_contextvars(**tenant_log_fields(context))
    try:
        yield
    finally:
        structlog.contextvars.reset_contextvars(**tokens)
