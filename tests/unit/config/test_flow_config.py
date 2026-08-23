"""Strict Flow configuration and startup validation tests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import (
    FlowRuntimeConfig,
    GatewayConfig,
)
from z_llm_safety_gateway.config.validators import validate_config
from z_llm_safety_gateway.flow.contracts import (
    CapabilityNodeDefinition,
    FlowDefinition,
)
from z_llm_safety_gateway.flow.legacy import compile_legacy_detector_flows


def _base_config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {
                "name": "provider",
                "type": "openai",
                "base_url": "https://provider.invalid/v1",
                "api_key": "top-secret-api-key",
            }
        ],
        "routing": {"rules": [{"pattern": "*", "provider": "provider"}]},
        "pipeline": {},
    }
    config.update(overrides)
    return config


def _capability_node(node_id: str = "detector-node") -> dict[str, Any]:
    return {
        "kind": "capability",
        "contract_version": "1.0",
        "node_id": node_id,
        "capability_id": "detector.prompt_injection",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.detector-result.v1",
        "policy": {
            "timeout": {"seconds": 3, "action": "fail_closed"},
            "failure": {"action": "fail_closed"},
            "availability": {
                "required": True,
                "on_unavailable": "fail_closed",
                "on_circuit_open": "fail_closed",
            },
            "degradation": {
                "allowed": True,
                "emit_evidence": True,
                "emit_metrics": True,
            },
            "stop": {"signals": ["safety.block"]},
        },
    }


def _flow(
    flow_id: str = "input-safety",
    nodes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "flow_id": flow_id,
        "version": "1.0.0",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.detector-result.v1",
        "nodes": nodes if nodes is not None else [_capability_node()],
    }


def test_tc_cfg_001() -> None:
    """TC-CFG-001: strict new Flow config resolves stage refs and complete policy."""
    config = GatewayConfig.model_validate(
        _base_config(
            flow_runtime={
                "max_depth": 8,
                "max_nodes": 256,
                "max_concurrency": 64,
                "default_timeout": 30,
                "absolute_timeout": 120,
                "max_evidence_size": 262144,
            },
            flows=[_flow()],
            pipeline={"input_flow": {"flow_id": "input-safety", "version": "1.0.0"}},
        )
    )

    assert isinstance(config.flow_runtime, FlowRuntimeConfig)
    assert isinstance(config.flows[0], FlowDefinition)
    assert isinstance(config.flows[0].nodes[0], CapabilityNodeDefinition)
    assert config.pipeline.input_flow is not None
    assert config.pipeline.input_flow.flow_id == "input-safety"
    policy = config.resolved_flow_policies[("input-safety", "1.0.0", "detector-node")]
    assert policy.timeout.seconds == 3
    assert policy.availability.required is True
    assert set(policy.sources.model_dump().values()) == {"explicit"}


def test_tc_cfg_002() -> None:
    """TC-CFG-002: explicit flows and explicit legacy detectors are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GatewayConfig.model_validate(
            _base_config(
                flows=[_flow()],
                pipeline={
                    "input_flow": {"flow_id": "input-safety", "version": "1.0.0"},
                    "detectors": {"input": [], "output": []},
                },
            )
        )
    assert "conflicting_flow_sources" in str(exc_info.value)

    no_explicit_detectors = GatewayConfig.model_validate(
        _base_config(
            flows=[_flow()],
            pipeline={"input_flow": {"flow_id": "input-safety", "version": "1.0.0"}},
        )
    )
    assert no_explicit_detectors.pipeline.detectors.input == []


def test_tc_cfg_003() -> None:
    """TC-CFG-003: flat and bidirectional legacy YAML compile without Flow fields."""
    with pytest.warns(UserWarning, match="flat list"):
        flat = GatewayConfig.model_validate(
            _base_config(
                pipeline={
                    "detectors": [
                        {
                            "name": "prompt_injection",
                            "block_threshold": 0.9,
                            "flag_threshold": 0.6,
                            "required": True,
                            "on_error": "fail_closed",
                        }
                    ]
                }
            )
        )
    compiled_flat = compile_legacy_detector_flows(flat)
    assert compiled_flat.input_flow.flow_id == "legacy-input-detector-flow"
    assert compiled_flat.output_flow.flow_id == "legacy-output-detector-flow"
    assert compiled_flat.detector_config("input", "prompt_injection").config == {
        "block_threshold": 0.9,
        "flag_threshold": 0.6,
    }

    bidirectional = GatewayConfig.model_validate(
        _base_config(
            pipeline={
                "detectors": {
                    "input": [{"name": "prompt_injection"}],
                    "output": [{"name": "secret_leak"}],
                }
            }
        )
    )
    compiled_bidirectional = compile_legacy_detector_flows(bidirectional)
    assert [node.node_id for node in compiled_bidirectional.input_flow.nodes] == [
        "input-prompt_injection"
    ]
    assert [node.node_id for node in compiled_bidirectional.output_flow.nodes] == [
        "output-secret_leak"
    ]


def test_tc_cfg_004() -> None:
    """TC-CFG-004: omitted legacy fields use existing defaults with legacy_default source."""
    config = GatewayConfig.model_validate(
        _base_config(
            security={"timeout": {"detector": "9s"}},
            pipeline={
                "sync_timeout": "7s",
                "detectors": {"input": [{"name": "prompt_injection"}], "output": []},
            },
        )
    )
    compiled = compile_legacy_detector_flows(config)
    policy = compiled.policy("legacy-input-detector-flow", "input-prompt_injection")

    assert policy.timeout.seconds == 9
    assert policy.failure.action == "fail_open"
    assert policy.availability.required is False
    assert policy.stop.signals == ("safety.block",)
    assert set(policy.sources.model_dump().values()) == {"legacy_default"}
    assert compiled.output_sync_timeout_seconds == 7


def test_tc_cfg_005() -> None:
    """TC-CFG-005: startup rejects refs, cycles, limits, versions, and policy conflicts."""
    unknown_ref = _base_config(
        flows=[_flow()],
        pipeline={"input_flow": {"flow_id": "missing-flow", "version": "1.0.0"}},
    )
    with pytest.raises(ValidationError) as unknown_error:
        GatewayConfig.model_validate(unknown_ref)
    assert "flow_reference_not_found" in str(unknown_error.value)
    assert "top-secret-api-key" not in str(unknown_error.value)

    with pytest.raises(ValidationError, match="explicit_flow_stage_reference_required"):
        GatewayConfig.model_validate(_base_config(flows=[_flow()]))

    unknown_reducer = _flow()
    unknown_reducer["reducer_capability_id"] = "unknown-reducer"
    with pytest.raises(ValidationError, match="reducer_capability_not_found"):
        GatewayConfig.model_validate(
            _base_config(
                flows=[unknown_reducer],
                pipeline={
                    "input_flow": {"flow_id": "input-safety", "version": "1.0.0"}
                },
            )
        )

    to_b = {
        "kind": "flow",
        "contract_version": "1.0",
        "node_id": "to-b",
        "flow_id": "flow-b",
        "flow_version": "1.0.0",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.detector-result.v1",
    }
    to_a = {**to_b, "node_id": "to-a", "flow_id": "flow-a"}
    with pytest.raises(ValidationError) as cycle_error:
        GatewayConfig.model_validate(
            _base_config(flows=[_flow("flow-a", [to_b]), _flow("flow-b", [to_a])])
        )
    assert "flow_cycle" in str(cycle_error.value)

    with pytest.raises(ValidationError) as limit_error:
        GatewayConfig.model_validate(
            _base_config(
                flow_runtime={"max_nodes": 1},
                flows=[_flow(nodes=[_capability_node("one"), _capability_node("two")])],
            )
        )
    assert "flow_node_limit_exceeded" in str(limit_error.value)

    incompatible = _flow()
    incompatible["contract_version"] = "2.0"
    with pytest.raises(ValidationError) as version_error:
        GatewayConfig.model_validate(_base_config(flows=[incompatible]))
    assert "incompatible_contract_version" in str(version_error.value)

    conflicting_node = _capability_node()
    conflicting_node["policy"]["availability"] = {
        "required": True,
        "on_unavailable": "fail_open",
        "on_circuit_open": "fail_closed",
    }
    with pytest.raises(ValidationError) as policy_error:
        GatewayConfig.model_validate(_base_config(flows=[_flow(nodes=[conflicting_node])]))
    assert "policy_conflict" in str(policy_error.value)

    first = str(policy_error.value)
    with pytest.raises(ValidationError) as repeated_error:
        GatewayConfig.model_validate(_base_config(flows=[_flow(nodes=[conflicting_node])]))
    assert str(repeated_error.value) == first


def test_tc_cfg_006() -> None:
    """TC-CFG-006: documented Flow YAML is validated by the real runtime models."""
    documentation = Path("docs/configuration.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- FLOW_CONFIG_EXAMPLE_START -->\s*```yaml\s*(.*?)\s*```\s*"
        r"<!-- FLOW_CONFIG_EXAMPLE_END -->",
        documentation,
        flags=re.DOTALL,
    )
    assert match is not None
    documented_config = yaml.safe_load(match.group(1))
    config = GatewayConfig.model_validate(documented_config)

    assert config.pipeline.input_flow is not None
    assert config.pipeline.input_flow.flow_id == "input-safety"
    assert config.flow_runtime.max_evidence_size == 262144
    assert config.providers[0].api_key == ""

    legacy = GatewayConfig.model_validate(_base_config())
    assert legacy.flows == ()
    assert legacy.pipeline.input_flow is None
    assert legacy.pipeline.output_flow is None


@pytest.mark.parametrize("max_evidence_size", [1024, 262143, 262145])
def test_flow_evidence_budget_must_equal_representable_limit(
    max_evidence_size: int,
) -> None:
    """Startup rejects evidence budgets that cannot honor the fixed envelope contract."""
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(
            _base_config(flow_runtime={"max_evidence_size": max_evidence_size})
        )


def test_explicit_capability_binding_supports_private_grpc_config() -> None:
    flow = _flow()
    flow["nodes"][0]["capability_id"] = "detector.acme_guard"
    secret = "binding-secret-token"
    config = GatewayConfig.model_validate(
        _base_config(
            flows=[flow],
            capabilities=[
                {
                    "capability_id": "detector.acme_guard",
                    "detector_name": "acme_guard",
                    "type": "grpc",
                    "config": {
                        "endpoint": "127.0.0.1:50051",
                        "api_key": secret,
                    },
                }
            ],
            pipeline={
                "input_flow": {"flow_id": "input-safety", "version": "1.0.0"}
            },
        )
    )

    validate_config(config)
    assert config.capabilities[0].config["api_key"] == secret
    assert secret not in repr(config.capabilities[0])
