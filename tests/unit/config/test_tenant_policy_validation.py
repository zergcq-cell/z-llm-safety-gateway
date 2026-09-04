"""Cross-field startup validation for tenant policy declarations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import GatewayConfig
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.exceptions import ConfigValidationError


def _capability_node() -> dict[str, Any]:
    return {
        "kind": "capability",
        "contract_version": "1.0",
        "node_id": "prompt-check",
        "capability_id": "detector.prompt_injection",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.detector-result.v1",
        "policy": {},
    }


def _flow() -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "flow_id": "tenant-input",
        "version": "1.0.0",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.detector-result.v1",
        "nodes": [_capability_node()],
    }


def _binding(capability_id: str = "detector.prompt_injection") -> dict[str, Any]:
    return {
        "capability_id": capability_id,
        "detector_name": capability_id.removeprefix("detector."),
        "config": {},
    }


def _data() -> dict[str, Any]:
    return {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "local",
                "type": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "api_key": "provider-secret-must-not-leak",
            },
            {
                "name": "backup",
                "type": "openai_compatible",
                "base_url": "http://localhost:11435/v1",
            },
        ],
        "routing": {},
        "flows": [_flow()],
        "tenancy": {
            "enabled": True,
            "tenants": [{"id": "acme", "policy_id": "acme-policy"}],
            "policies": [
                {
                    "id": "acme-policy",
                    "input_flow": {
                        "flow_id": "tenant-input",
                        "version": "1.0.0",
                    },
                    "output_flow": None,
                    "capabilities": [_binding()],
                    "routing": {
                        "models_provider": "local",
                        "rules": [{"pattern": "gpt-*", "provider": "local"}],
                    },
                }
            ],
        },
        "security": {
            "auth": {
                "enabled": True,
                "api_keys": [
                    {"key": "tenant-secret", "name": "app", "tenant_id": "acme"}
                ],
            }
        },
    }


@pytest.mark.parametrize(
    ("invalid_case", "reason_code"),
    (
        ("unknown_flow", "tenant_policy_flow_not_found"),
        ("missing_binding", "tenant_policy_capability_binding_missing"),
        ("duplicate_binding", "duplicate_capability_binding"),
        ("unused_binding", "tenant_policy_capability_binding_unused"),
    ),
)
def test_tenant_policy_flow_and_binding_references_fail_closed(
    invalid_case: str,
    reason_code: str,
) -> None:
    """TC-TCC-011: Selected Flows have exactly one policy-local binding."""
    data = _data()
    policy = data["tenancy"]["policies"][0]
    if invalid_case == "unknown_flow":
        policy["input_flow"]["flow_id"] = "missing-flow"
    elif invalid_case == "missing_binding":
        policy["capabilities"] = []
    elif invalid_case == "duplicate_binding":
        policy["capabilities"].append(deepcopy(policy["capabilities"][0]))
    else:
        policy["input_flow"] = None

    config = GatewayConfig.model_validate(data)
    with pytest.raises(ConfigValidationError, match=reason_code) as exc_info:
        validate_config(config)

    assert "provider-secret-must-not-leak" not in str(exc_info.value)
    assert "tenant-secret" not in str(exc_info.value)


def test_tenant_policy_reuses_nested_flow_graph_limits() -> None:
    """TC-TCC-011: Nested tenant Flows retain the existing graph validation."""
    data = _data()
    data["flows"][0]["nodes"] = [
        {
            "kind": "flow",
            "contract_version": "1.0",
            "node_id": "missing-child",
            "flow_id": "unknown-child",
            "flow_version": "1.0.0",
            "input_schema": "safety.text.v1",
            "output_schema": "safety.detector-result.v1",
            "policy": {},
        }
    ]

    with pytest.raises(ValidationError, match="flow_reference_not_found"):
        GatewayConfig.model_validate(data)


@pytest.mark.parametrize(
    ("invalid_case", "reason_code"),
    (
        ("unknown_provider", "tenant_policy_route_provider_not_found"),
        ("route_conflict", "tenant_policy_route_conflict"),
        ("models_not_allowed", "tenant_policy_models_provider_not_allowed"),
    ),
)
def test_tenant_policy_routing_references_fail_closed(
    invalid_case: str,
    reason_code: str,
) -> None:
    """TC-TCC-012: Tenant routes form one explicit bounded Provider domain."""
    data = _data()
    routing = data["tenancy"]["policies"][0]["routing"]
    if invalid_case == "unknown_provider":
        routing["rules"][0]["provider"] = "missing-provider"
    elif invalid_case == "route_conflict":
        routing["rules"].append({"pattern": "gpt-*", "provider": "backup"})
    else:
        routing["models_provider"] = "backup"

    config = GatewayConfig.model_validate(data)
    with pytest.raises(ConfigValidationError, match=reason_code) as exc_info:
        validate_config(config)

    assert "provider-secret-must-not-leak" not in str(exc_info.value)


def test_non_identical_route_overlap_keeps_declaration_order() -> None:
    """TC-TCC-012: Non-identical overlaps remain valid first-match rules."""
    data = _data()
    rules = data["tenancy"]["policies"][0]["routing"]["rules"]
    rules.append({"pattern": "gpt-4*", "provider": "backup"})

    config = GatewayConfig.model_validate(data)
    validate_config(config)

    assert [rule.pattern for rule in config.tenancy.policies[0].routing.rules] == [
        "gpt-*",
        "gpt-4*",
    ]


@pytest.mark.parametrize(
    "selector",
    ("routing", "detectors", "input_flow", "output_flow", "capabilities"),
)
def test_tenant_and_global_execution_selectors_conflict(selector: str) -> None:
    """TC-TCC-013: Tenant policies are the only multi-tenant selectors."""
    data = _data()
    if selector == "routing":
        data["routing"] = {"rules": [{"pattern": "*", "provider": "local"}]}
    elif selector == "capabilities":
        data["capabilities"] = []
    else:
        data.setdefault("pipeline", {})[selector] = (
            {"input": [], "output": []}
            if selector == "detectors"
            else {"flow_id": "tenant-input", "version": "1.0.0"}
        )

    with pytest.raises(ValidationError, match="conflicting_tenant_policy_sources"):
        GatewayConfig.model_validate(data)


def test_tenant_policies_allow_global_declaration_sources() -> None:
    """TC-TCC-013: Providers, Flows and runtime bounds remain global declarations."""
    data = _data()
    data["flow_runtime"] = {"max_depth": 8, "max_nodes": 256}

    config = GatewayConfig.model_validate(data)
    validate_config(config)

    assert len(config.providers) == 2
    assert len(config.flows) == 1


def test_tenant_detector_validation_never_echoes_raw_threshold_or_path() -> None:
    """TC-TCC-011: tenant validation errors keep raw Detector config private."""
    data = _data()
    private_threshold = 0.271828
    binding = data["tenancy"]["policies"][0]["capabilities"][0]
    binding["config"] = {
        "block_threshold": private_threshold,
        "flag_threshold": private_threshold,
        "word_list_file": "/private/deployment/topology/words.txt",
    }
    config = GatewayConfig.model_validate(data)

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    rendered = str(exc_info.value)
    assert str(private_threshold) not in rendered
    assert "/private/deployment" not in rendered
    assert "tenant_detector_threshold_conflict" in rendered


def test_invalid_tenant_flag_rule_fails_before_runtime_initialization() -> None:
    """TC-TCC-011: tenant reducer syntax is validated with a stable code."""
    data = _data()
    data["tenancy"]["policies"][0]["result_policy"] = {
        "flag_escalation": {
            "enabled": True,
            "rule": "private_invalid_rule",
            "action": "block",
        }
    }
    config = GatewayConfig.model_validate(data)

    with pytest.raises(ConfigValidationError, match="tenant_flag_escalation_invalid") as exc:
        validate_config(config)

    assert "private_invalid_rule" not in str(exc.value)
