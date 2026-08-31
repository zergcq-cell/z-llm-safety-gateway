"""Tenant identity configuration contract tests for public v0.3.0."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import GatewayConfig, TenancyConfig, TenantConfig
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _gateway_data(*, tenant_ids: tuple[str, ...] = ("acme",)) -> dict[str, Any]:
    return {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "local",
                "type": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
            }
        ],
        "routing": {"rules": [{"pattern": "*", "provider": "local"}]},
        "tenancy": {
            "enabled": True,
            "tenants": [{"id": tenant_id} for tenant_id in tenant_ids],
        },
        "security": {
            "auth": {
                "enabled": True,
                "api_keys": [
                    {
                        "key": f"secret-{tenant_id}",
                        "name": f"{tenant_id}-app",
                        "tenant_id": tenant_id,
                    }
                    for tenant_id in tenant_ids
                ],
            }
        },
    }


def test_valid_multi_tenant_config_contract() -> None:
    """TC-TCC-001: Valid strict tenant declarations and bindings parse."""
    config = GatewayConfig(**_gateway_data(tenant_ids=("acme", "globex_2")))

    assert config.tenancy.enabled is True
    assert tuple(tenant.id for tenant in config.tenancy.tenants) == ("acme", "globex_2")
    assert tuple(key.tenant_id for key in config.security.auth.api_keys) == (
        "acme",
        "globex_2",
    )

    with pytest.raises(ValidationError, match="extra_forbidden"):
        TenantConfig(id="acme", flow="must-not-be-accepted")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "tenant_id",
    (
        "",
        "Acme",
        "white space",
        "租户",
        "acme/path",
        "-acme",
        "acme_",
        "a" * 65,
    ),
)
def test_tenant_id_rejects_invalid_values(tenant_id: str) -> None:
    """TC-TCC-002: Invalid or ambiguous tenant IDs fail schema validation."""
    secret = "secret-that-must-not-appear"
    data = _gateway_data()
    data["tenancy"]["tenants"][0]["id"] = tenant_id
    data["security"]["auth"]["api_keys"][0]["key"] = secret
    with pytest.raises(ValidationError) as exc_info:
        GatewayConfig(**data)

    message = str(exc_info.value)
    assert "id" in message
    assert secret not in message


@pytest.mark.parametrize(
    ("tenant_count", "key_count", "reason_code"),
    (
        (1025, 1, "tenant_limit_exceeded"),
        (1, 4097, "tenant_api_key_limit_exceeded"),
    ),
)
def test_tenant_and_key_limits(
    tenant_count: int,
    key_count: int,
    reason_code: str,
) -> None:
    """TC-TCC-003: Multi-tenant declaration cardinality is bounded."""
    data = _gateway_data()
    data["tenancy"]["tenants"] = [
        {"id": f"tenant-{index}"} for index in range(tenant_count)
    ]
    data["security"]["auth"]["api_keys"] = [
        {
            "key": f"secret-{index}",
            "name": f"app-{index}",
            "tenant_id": "acme",
        }
        for index in range(key_count)
    ]

    with pytest.raises(ValidationError, match=reason_code):
        GatewayConfig(**data)


@pytest.mark.parametrize("coerced_enabled", (1, "true", "yes"))
def test_tenancy_enabled_rejects_coerced_boolean(coerced_enabled: object) -> None:
    """The bounded tenancy branch cannot be reached through boolean coercion."""
    data = _gateway_data()
    data["tenancy"]["enabled"] = coerced_enabled

    with pytest.raises(ValidationError, match="bool_type"):
        GatewayConfig(**data)


def test_tenancy_contract_contains_identity_only() -> None:
    """TC-TCC-007: Tenant schema cannot absorb later v0.3 policy fields."""
    assert set(TenancyConfig.model_fields) == {"enabled", "tenants"}
    assert set(TenantConfig.model_fields) == {"id"}

    forbidden_policy_fields = {
        "flows",
        "detectors",
        "provider",
        "audit",
        "metrics",
        "rate_limit",
    }
    assert forbidden_policy_fields.isdisjoint(TenancyConfig.model_fields)


@pytest.mark.parametrize(
    ("invalid_case", "reason_code"),
    (
        ("auth_disabled", "tenancy_enabled_requires_auth"),
        ("empty_tenants", "tenancy_requires_tenants"),
        ("missing_tenant_id", "api_key_tenant_required"),
    ),
)
def test_required_multi_tenant_fields_fail_closed(
    invalid_case: str,
    reason_code: str,
) -> None:
    """TC-TCC-004: Required multi-tenant fields fail with stable codes."""
    data = _gateway_data()
    if invalid_case == "auth_disabled":
        data["security"]["auth"]["enabled"] = False
    elif invalid_case == "empty_tenants":
        data["tenancy"]["tenants"] = []
    else:
        del data["security"]["auth"]["api_keys"][0]["tenant_id"]

    with pytest.raises(ConfigValidationError, match=reason_code):
        validate_config(GatewayConfig(**data))


@pytest.mark.parametrize(
    ("invalid_case", "reason_code"),
    (
        ("duplicate_tenant", "duplicate_tenant_id"),
        ("unknown_tenant", "unknown_api_key_tenant"),
        ("duplicate_key", "duplicate_api_key"),
        ("empty_key", "invalid_api_key"),
        ("unreachable_key", "invalid_api_key"),
        ("duplicate_name", "invalid_api_key_name"),
        ("empty_name", "invalid_api_key_name"),
        ("tenant_without_key", "tenant_without_api_key"),
    ),
)
def test_ambiguous_bindings_fail_closed_without_secret_leak(
    invalid_case: str,
    reason_code: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-TCC-005: Ambiguous bindings fail closed without key disclosure."""
    secret = "never-log-this-api-key"
    data = _gateway_data(tenant_ids=("acme", "globex"))
    keys = data["security"]["auth"]["api_keys"]
    keys[0]["key"] = secret
    if invalid_case == "duplicate_tenant":
        data["tenancy"]["tenants"] = [{"id": "acme"}, {"id": "acme"}]
    elif invalid_case == "unknown_tenant":
        keys[0]["tenant_id"] = "unknown"
    elif invalid_case == "duplicate_key":
        keys[1]["key"] = secret
    elif invalid_case == "empty_key":
        keys[0]["key"] = ""
    elif invalid_case == "unreachable_key":
        keys[0]["key"] = "   "
    elif invalid_case == "duplicate_name":
        keys[1]["name"] = keys[0]["name"]
    elif invalid_case == "empty_name":
        keys[0]["name"] = "   "
    else:
        keys.pop()

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(GatewayConfig(**data))

    assert reason_code in str(exc_info.value)
    assert secret not in str(exc_info.value)
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_disabled_tenancy_rejects_tenant_fields_and_accepts_legacy() -> None:
    """TC-TCC-006: Disabled tenancy rejects contradictions, not legacy config."""
    with_tenants = _gateway_data()
    with_tenants["tenancy"]["enabled"] = False
    with_binding = _gateway_data()
    with_binding["tenancy"] = {"enabled": False}

    for data in (with_tenants, with_binding):
        with pytest.raises(
            ConfigValidationError,
            match="tenancy_disabled_with_tenant_configuration",
        ):
            validate_config(GatewayConfig(**data))

    legacy = _gateway_data()
    legacy.pop("tenancy")
    for api_key in legacy["security"]["auth"]["api_keys"]:
        api_key.pop("tenant_id")
    validate_config(GatewayConfig(**legacy))
