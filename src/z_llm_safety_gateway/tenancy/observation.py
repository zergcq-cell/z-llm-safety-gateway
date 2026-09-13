"""Trusted, payload-free observation identity for one tenant execution."""

from __future__ import annotations

from z_llm_safety_gateway.flow.observation import (
    ObservationScope,
    TenantObservationContext,
)
from z_llm_safety_gateway.tenancy.context import TenantContext
from z_llm_safety_gateway.tenancy.policy import TenantPolicyContext

__all__ = [
    "ObservationScope",
    "TenantObservationContext",
    "build_tenant_observation_context",
]


def build_tenant_observation_context(
    tenant: TenantContext | None,
    policy: TenantPolicyContext | None,
) -> TenantObservationContext:
    """Project matching trusted request identities into observable provenance."""
    if tenant is None or policy is None or tenant.tenant_id != policy.tenant_id:
        raise ValueError("tenant_context_invalid")
    return TenantObservationContext(
        scope=ObservationScope.TENANT,
        tenant_id=tenant.tenant_id,
        policy_id=policy.policy_id,
    )
