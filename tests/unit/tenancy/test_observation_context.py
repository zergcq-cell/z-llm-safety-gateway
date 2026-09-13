"""Tenant observation-context contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from z_llm_safety_gateway.tenancy.context import TenantContext
from z_llm_safety_gateway.tenancy.observation import (
    ObservationScope,
    TenantObservationContext,
    build_tenant_observation_context,
)
from z_llm_safety_gateway.tenancy.policy import TenantPolicyContext


def test_build_context_uses_only_trusted_identity_and_policy() -> None:
    """TC-TEC-001: Context is frozen, bounded, and secret-free."""
    context = build_tenant_observation_context(
        TenantContext("acme", "api_key"),
        TenantPolicyContext(
            tenant_id="acme",
            policy_id="strict-policy",
            input_flow_identity=None,
            output_flow_identity=None,
            routing_profile_id="strict-policy",
        ),
    )

    assert context == TenantObservationContext(
        scope=ObservationScope.TENANT,
        tenant_id="acme",
        policy_id="strict-policy",
    )
    assert context.contract_version == "1.0"
    assert "secret" not in repr(context)
    with pytest.raises(FrozenInstanceError):
        context.tenant_id = "globex"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("tenant", "policy"),
    (
        (None, None),
        (TenantContext("acme", "api_key"), None),
        (
            TenantContext("acme", "api_key"),
            TenantPolicyContext(
                tenant_id="globex",
                policy_id="strict-policy",
                input_flow_identity=None,
                output_flow_identity=None,
                routing_profile_id="strict-policy",
            ),
        ),
    ),
)
def test_build_context_rejects_missing_or_conflicting_trusted_state(
    tenant: TenantContext | None,
    policy: TenantPolicyContext | None,
) -> None:
    """TC-TEC-003: Invalid runtime state cannot be silently attributed."""
    with pytest.raises(ValueError, match="tenant_context_invalid"):
        build_tenant_observation_context(tenant, policy)


def test_non_request_contexts_have_no_tenant_identity() -> None:
    """TC-TEC-006: Legacy, system, and policy scopes cannot impersonate a tenant."""
    assert TenantObservationContext.legacy().tenant_id is None
    assert TenantObservationContext.system().policy_id is None
    policy = TenantObservationContext.policy("strict-policy")
    assert policy.scope is ObservationScope.POLICY
    assert policy.tenant_id is None
    assert policy.policy_id == "strict-policy"
