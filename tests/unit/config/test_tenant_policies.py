"""Tenant policy schema and identity-reference contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import GatewayConfig, TenantPolicyConfig
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _policy_data(*, shared: bool = False) -> dict[str, Any]:
    tenants = [
        {"id": "acme", "policy_id": "strict-chat"},
        {
            "id": "globex",
            "policy_id": "strict-chat" if shared else "research-chat",
        },
    ]
    policies = [
        {
            "id": "strict-chat",
            "input_flow": None,
            "output_flow": None,
            "capabilities": [],
            "result_policy": {},
            "routing": {
                "models_provider": "local",
                "rules": [{"pattern": "gpt-*", "provider": "local"}],
            },
        }
    ]
    if not shared:
        policies.append(
            {
                "id": "research-chat",
                "input_flow": None,
                "output_flow": None,
                "capabilities": [],
                "result_policy": {
                    "flag_escalation": {
                        "enabled": True,
                        "rule": "count >= 2",
                        "action": "block",
                    }
                },
                "routing": {
                    "models_provider": "local",
                    "rules": [{"pattern": "research-*", "provider": "local"}],
                },
            }
        )
    return {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "local",
                "type": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
            }
        ],
        "routing": {},
        "tenancy": {"enabled": True, "tenants": tenants, "policies": policies},
        "security": {
            "auth": {
                "enabled": True,
                "api_keys": [
                    {
                        "key": "secret-acme",
                        "name": "acme-app",
                        "tenant_id": "acme",
                    },
                    {
                        "key": "secret-globex",
                        "name": "globex-app",
                        "tenant_id": "globex",
                    },
                ],
            }
        },
    }


def test_valid_strict_tenant_policy_schema() -> None:
    """TC-TCC-008: Policy stages, bindings, result policy, and routing are strict."""
    config = GatewayConfig(**_policy_data())

    assert tuple(tenant.policy_id for tenant in config.tenancy.tenants) == (
        "strict-chat",
        "research-chat",
    )
    strict = config.tenancy.policies[0]
    assert strict.input_flow is None
    assert strict.output_flow is None
    assert strict.capabilities == ()
    assert strict.routing.models_provider == "local"
    assert strict.routing.rules[0].pattern == "gpt-*"
    assert config.tenancy.policies[1].result_policy.flag_escalation is not None

    missing_stage = deepcopy(_policy_data())
    del missing_stage["tenancy"]["policies"][0]["input_flow"]
    with pytest.raises(ValidationError, match="input_flow"):
        GatewayConfig(**missing_stage)

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TenantPolicyConfig.model_validate(
            {**_policy_data()["tenancy"]["policies"][0], "audit": {}}
        )


@pytest.mark.parametrize(
    ("limit_kind", "reason_code"),
    (
        ("policies", "tenant_policy_limit_exceeded"),
        ("bindings", "tenant_policy_capability_limit_exceeded"),
        ("rules", "tenant_policy_route_limit_exceeded"),
    ),
)
def test_policy_reuse_and_declaration_limits(
    limit_kind: str,
    reason_code: str,
) -> None:
    """TC-TCC-009: Shared policy is explicit and declarations are bounded."""
    shared = GatewayConfig(**_policy_data(shared=True))
    assert len(shared.tenancy.policies) == 1
    assert {tenant.policy_id for tenant in shared.tenancy.tenants} == {"strict-chat"}

    data = _policy_data(shared=True)
    policy = data["tenancy"]["policies"][0]
    if limit_kind == "policies":
        data["tenancy"]["policies"] = [
            {**deepcopy(policy), "id": f"policy-{index}"}
            for index in range(1025)
        ]
    elif limit_kind == "bindings":
        policy["capabilities"] = [
            {
                "capability_id": f"detector.detector-{index}",
                "detector_name": f"detector-{index}",
            }
            for index in range(257)
        ]
    else:
        policy["routing"]["rules"] = [
            {"pattern": f"model-{index}", "provider": "local"}
            for index in range(257)
        ]

    with pytest.raises(ValidationError, match=reason_code):
        GatewayConfig(**data)


@pytest.mark.parametrize(
    ("invalid_case", "reason_code"),
    (
        ("empty_policies", "tenant_policy_required"),
        ("missing_policy_id", "tenant_policy_required"),
        ("duplicate_policy", "duplicate_tenant_policy_id"),
        ("unknown_policy", "unknown_tenant_policy"),
    ),
)
def test_policy_identity_failures_use_stable_codes(
    invalid_case: str,
    reason_code: str,
) -> None:
    """TC-TCC-010: Missing, duplicate, and unknown policy refs fail closed."""
    data = _policy_data()
    if invalid_case == "empty_policies":
        data["tenancy"]["policies"] = []
    elif invalid_case == "missing_policy_id":
        del data["tenancy"]["tenants"][0]["policy_id"]
    elif invalid_case == "duplicate_policy":
        data["tenancy"]["policies"][1]["id"] = "strict-chat"
    else:
        data["tenancy"]["tenants"][0]["policy_id"] = "unknown"

    with pytest.raises(ConfigValidationError, match=reason_code):
        validate_config(GatewayConfig(**data))


def test_disabled_tenancy_policy_compatibility() -> None:
    """TC-TCC-014: Disabled tenancy rejects policy fields, not legacy config."""
    with_policy = _policy_data(shared=True)
    with_policy["tenancy"]["enabled"] = False
    with pytest.raises(
        ConfigValidationError,
        match="tenancy_disabled_with_tenant_policy",
    ):
        validate_config(GatewayConfig(**with_policy))

    legacy = _policy_data(shared=True)
    legacy.pop("tenancy")
    for api_key in legacy["security"]["auth"]["api_keys"]:
        api_key.pop("tenant_id")
    validate_config(GatewayConfig(**legacy))
