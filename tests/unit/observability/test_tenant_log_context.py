"""Tenant log scope lifecycle tests."""

from __future__ import annotations

import pytest
import structlog

from z_llm_safety_gateway.observability.tenant import bound_tenant_observation
from z_llm_safety_gateway.tenancy.observation import (
    ObservationScope,
    TenantObservationContext,
)


def test_bound_tenant_observation_restores_context_after_exit() -> None:
    """TC-TEC-005/TOB-003: task-local log fields cannot leak to later work."""
    structlog.contextvars.clear_contextvars()
    context = TenantObservationContext(ObservationScope.TENANT, "acme", "strict")

    with bound_tenant_observation(context):
        assert structlog.contextvars.get_contextvars() == {
            "tenant_scope": "tenant",
            "tenant_id": "acme",
            "tenant_policy_id": "strict",
        }

    assert structlog.contextvars.get_contextvars() == {}


def test_tenant_trace_projection_omits_invalid_values() -> None:
    """TC-TOB-005: arbitrary values are rejected before projection."""
    with pytest.raises(ValueError, match="tenant_context_invalid"):
        TenantObservationContext(
            ObservationScope.TENANT, "secret content", "https://private/key"
        )
