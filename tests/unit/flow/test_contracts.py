"""Flow, Node, and Capability contract tests for Flow Foundation."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from z_llm_safety_gateway.flow.contracts import (
    CapabilityDescriptor,
    CapabilityNodeDefinition,
    FlowContext,
    FlowContractError,
    FlowContractRegistry,
    FlowDefinition,
    FlowInput,
    FlowItem,
    FlowNodeDefinition,
)


def _capability(**overrides: Any) -> CapabilityDescriptor:
    values: dict[str, Any] = {
        "contract_version": "1.0",
        "capability_id": "detector.test",
        "implementation_version": "plugin-build-7",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.signal.v1",
    }
    values.update(overrides)
    return CapabilityDescriptor(**values)


def _capability_node(**overrides: Any) -> CapabilityNodeDefinition:
    values: dict[str, Any] = {
        "contract_version": "1.0",
        "node_id": "detect-content",
        "capability_id": "detector.test",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.signal.v1",
        "priority": 20,
        "policy": {"timeout": {"seconds": 5.0}},
    }
    values.update(overrides)
    return CapabilityNodeDefinition(**values)


def _flow(
    *nodes: CapabilityNodeDefinition | FlowNodeDefinition, **overrides: Any
) -> FlowDefinition:
    values: dict[str, Any] = {
        "contract_version": "1.0",
        "flow_id": "safety-flow",
        "version": "1.2.3",
        "input_schema": "safety.text.v1",
        "output_schema": "safety.signal.v1",
        "nodes": nodes,
    }
    values.update(overrides)
    return FlowDefinition(**values)


def test_tc_fc_001() -> None:
    """TC-FC-001: supported contracts retain contract and implementation versions."""
    capability = _capability()
    node = _capability_node()
    flow = _flow(node)
    registry = FlowContractRegistry(capabilities=(capability,), flows=(flow,))

    assert capability.contract_version == "1.0"
    assert capability.implementation_version == "plugin-build-7"
    assert node.contract_version == "1.0"
    assert flow.contract_version == "1.0"
    assert flow.version == "1.2.3"
    assert registry.resolve_capability(node) is capability


@pytest.mark.parametrize("unsupported", ["2.0", "1.1", "garbage"])
def test_tc_fc_002(unsupported: str) -> None:
    """TC-FC-002: unsupported contract versions fail with a stable diagnostic."""
    with pytest.raises(ValidationError) as exc_info:
        CapabilityDescriptor(
            contract_version=unsupported,
            capability_id="detector.safe-id",
            implementation_version="secret-implementation-value",
            input_schema="safety.text.v1",
            output_schema="safety.signal.v1",
        )

    diagnostic = str(exc_info.value)
    assert "incompatible_contract_version" in diagnostic
    assert "CapabilityDescriptor" in diagnostic
    assert "detector.safe-id" in diagnostic
    assert "secret-implementation-value" not in diagnostic


def test_tc_fc_003() -> None:
    """TC-FC-003: new Flow contracts reject unknown fields and invalid identities."""
    with pytest.raises(ValidationError) as unknown_error:
        FlowDefinition.model_validate(
            {
                "contract_version": "1.0",
                "flow_id": "strict-flow",
                "version": "1.0.0",
                "input_schema": "safety.text.v1",
                "output_schema": "safety.signal.v1",
                "nodes": [],
                "unknown_security_policy": "ignore-me",
            }
        )
    assert "extra_forbidden" in str(unknown_error.value)

    duplicate = _capability_node()
    with pytest.raises(ValidationError) as duplicate_error:
        _flow(duplicate, duplicate)
    assert "duplicate_node_id" in str(duplicate_error.value)

    with pytest.raises(ValidationError) as id_error:
        _flow(flow_id="x" * 129)
    assert "invalid_contract_id" in str(id_error.value)

    with pytest.raises(ValidationError) as version_error:
        _flow(version="not-semver")
    assert "invalid_semver" in str(version_error.value)


def test_tc_fc_004() -> None:
    """TC-FC-004: capability nodes bind exact descriptors and preserve policy metadata."""
    capability = _capability()
    node = _capability_node()
    flow = _flow(node)
    registry = FlowContractRegistry(capabilities=(capability,), flows=(flow,))

    assert registry.resolve_capability(node) is capability
    assert node.priority == 20
    assert node.policy == {"timeout": {"seconds": 5.0}}

    mismatched = _capability_node(input_schema="unexpected.schema.v1")
    with pytest.raises(FlowContractError) as exc_info:
        FlowContractRegistry(capabilities=(capability,), flows=(_flow(mismatched),))
    assert exc_info.value.code == "capability_schema_mismatch"
    assert exc_info.value.flow_id == "safety-flow"
    assert exc_info.value.node_id == "detect-content"


def test_tc_fc_005() -> None:
    """TC-FC-005: nested Flow refs are exact, acyclic, and bounded to depth eight."""
    child = _flow(flow_id="child-flow", version="1.0.0")
    nested = FlowNodeDefinition(
        contract_version="1.0",
        node_id="nested-child",
        flow_id="child-flow",
        flow_version="1.0.0",
        input_schema="safety.text.v1",
        output_schema="safety.signal.v1",
    )
    parent = _flow(nested, flow_id="parent-flow", version="1.0.0")
    registry = FlowContractRegistry(capabilities=(), flows=(parent, child))
    assert registry.resolve_flow(nested) is child

    missing = nested.model_copy(update={"flow_version": "2.0.0"})
    with pytest.raises(FlowContractError) as missing_error:
        FlowContractRegistry(capabilities=(), flows=(_flow(missing), child))
    assert missing_error.value.code == "flow_reference_not_found"

    cycle_a = _flow(
        nested.model_copy(update={"node_id": "to-b", "flow_id": "cycle-b"}),
        flow_id="cycle-a",
        version="1.0.0",
    )
    cycle_b = _flow(
        nested.model_copy(update={"node_id": "to-a", "flow_id": "cycle-a"}),
        flow_id="cycle-b",
        version="1.0.0",
    )
    with pytest.raises(FlowContractError) as cycle_error:
        FlowContractRegistry(capabilities=(), flows=(cycle_a, cycle_b))
    assert cycle_error.value.code == "flow_cycle"

    chain: list[FlowDefinition] = []
    for index in range(10):
        nodes: tuple[FlowNodeDefinition, ...] = ()
        if index < 9:
            nodes = (
                nested.model_copy(
                    update={
                        "node_id": f"to-{index + 1}",
                        "flow_id": f"depth-{index + 1}",
                    }
                ),
            )
        chain.append(_flow(*nodes, flow_id=f"depth-{index}", version="1.0.0"))
    with pytest.raises(FlowContractError) as depth_error:
        FlowContractRegistry(capabilities=(), flows=tuple(chain), max_depth=8)
    assert depth_error.value.code == "flow_depth_exceeded"


def test_tc_fc_006() -> None:
    """TC-FC-006: ordered input and immutable context propagate without payload evidence."""
    flow_input = FlowInput(
        contract_version="1.0",
        items=(
            FlowItem(item_id="item-0", content="secret-first"),
            FlowItem(item_id="item-1", content="secret-second"),
        ),
        context=FlowContext(
            request_id="request-7",
            correlation_id="correlation-7",
            direction="output",
            stage="sync-output",
            metadata={"tenant": "alpha"},
        ),
    )

    child_input = flow_input.for_child(
        parent_execution_id="flow-execution-parent",
        stage="nested-flow",
    )

    assert [item.item_id for item in child_input.items] == ["item-0", "item-1"]
    assert child_input.context.correlation_id == "correlation-7"
    assert child_input.context.parent_execution_id == "flow-execution-parent"
    with pytest.raises(ValidationError):
        child_input.context.stage = "mutated"  # type: ignore[misc]
    with pytest.raises(TypeError):
        child_input.context.metadata["tenant"] = "mutated"  # type: ignore[index]

    evidence = child_input.evidence_envelope().model_dump(mode="json")
    assert evidence["item_count"] == 2
    assert evidence["request_id"] == "request-7"
    assert "items" not in evidence
    assert "metadata" not in evidence
    assert "secret-first" not in repr(evidence)
    assert "secret-second" not in repr(evidence)
