"""Strict, versioned contracts for Flow, Node, and Capability objects."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SUPPORTED_CONTRACT_VERSIONS = frozenset({"1.0"})
DEFAULT_MAX_FLOW_DEPTH = 8
DEFAULT_MAX_EXPANDED_NODES = 256

_CONTRACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _validate_contract_id(value: str) -> str:
    if not _CONTRACT_ID_PATTERN.fullmatch(value):
        raise ValueError("invalid_contract_id")
    return value


def _validate_non_empty_bounded(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise ValueError("invalid_non_empty_value")
    return normalized


ContractId = Annotated[str, AfterValidator(_validate_contract_id)]
NonEmptyBoundedString = Annotated[str, AfterValidator(_validate_non_empty_bounded)]


class _StrictContract(BaseModel):
    """Base for externally supplied Flow contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class _VersionedContract(_StrictContract):
    """A contract accepted only when its exact schema version is supported."""

    contract_version: str

    @model_validator(mode="after")
    def _validate_contract_version(self) -> _VersionedContract:
        if self.contract_version not in SUPPORTED_CONTRACT_VERSIONS:
            identity = self._contract_identity()
            raise ValueError(
                "incompatible_contract_version: "
                f"object_type={type(self).__name__}, object_id={identity}"
            )
        return self

    def _contract_identity(self) -> str:
        for field_name in ("capability_id", "flow_id", "node_id", "item_id"):
            value = getattr(self, field_name, None)
            if isinstance(value, str):
                return value
        return "unknown"


class CapabilityDescriptor(_VersionedContract):
    """Stable metadata used to bind a Flow Node to a Capability implementation."""

    capability_id: ContractId
    implementation_version: NonEmptyBoundedString
    input_schema: ContractId
    output_schema: ContractId
    name: NonEmptyBoundedString | None = None
    category: NonEmptyBoundedString | None = None


class CapabilityNodeDefinition(_VersionedContract):
    """A Node that invokes one registered Capability."""

    kind: Literal["capability"] = "capability"
    node_id: ContractId
    capability_id: ContractId
    input_schema: ContractId
    output_schema: ContractId
    priority: int = 0
    policy: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("policy", mode="after")
    @classmethod
    def _freeze_policy(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return MappingProxyType(dict(value))


class FlowNodeDefinition(_VersionedContract):
    """A Node that invokes an exact version of another Flow."""

    kind: Literal["flow"] = "flow"
    node_id: ContractId
    flow_id: ContractId
    flow_version: str
    input_schema: ContractId
    output_schema: ContractId
    priority: int = 0
    policy: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("flow_version")
    @classmethod
    def _validate_flow_version(cls, value: str) -> str:
        if not _SEMVER_PATTERN.fullmatch(value):
            raise ValueError("invalid_semver")
        return value

    @field_validator("policy", mode="after")
    @classmethod
    def _freeze_policy(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return MappingProxyType(dict(value))


NodeDefinition = Annotated[
    CapabilityNodeDefinition | FlowNodeDefinition,
    Field(discriminator="kind"),
]


class FlowDefinition(_VersionedContract):
    """A versioned, ordered collection of Capability and nested Flow Nodes."""

    flow_id: ContractId
    version: str
    input_schema: ContractId
    output_schema: ContractId
    nodes: tuple[NodeDefinition, ...] = ()
    reducer_capability_id: ContractId | None = None

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not _SEMVER_PATTERN.fullmatch(value):
            raise ValueError("invalid_semver")
        return value

    @model_validator(mode="after")
    def _validate_unique_nodes(self) -> FlowDefinition:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError(f"duplicate_node_id: flow_id={self.flow_id}")
        return self


class FlowItem(_StrictContract):
    """One ordered in-memory item supplied to a Flow."""

    item_id: ContractId
    content: str
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="after")
    @classmethod
    def _freeze_metadata(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return MappingProxyType(dict(value))


class FlowContext(_StrictContract):
    """Immutable request-scoped context propagated to every Node."""

    request_id: NonEmptyBoundedString
    correlation_id: NonEmptyBoundedString
    direction: Literal["input", "output"]
    stage: NonEmptyBoundedString
    parent_execution_id: NonEmptyBoundedString | None = None
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="after")
    @classmethod
    def _freeze_metadata(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return MappingProxyType(dict(value))


class FlowEvidenceEnvelope(_VersionedContract):
    """Payload-free Flow input identity safe to attach to core evidence."""

    request_id: NonEmptyBoundedString
    correlation_id: NonEmptyBoundedString
    direction: Literal["input", "output"]
    stage: NonEmptyBoundedString
    parent_execution_id: NonEmptyBoundedString | None = None
    item_count: int = Field(ge=0)


class FlowInput(_VersionedContract):
    """Ordered Flow input and immutable request context."""

    items: tuple[FlowItem, ...]
    context: FlowContext

    def for_child(self, *, parent_execution_id: str, stage: str) -> FlowInput:
        """Return a child envelope with the same ordered items and correlation context."""
        child_context = self.context.model_copy(
            update={"parent_execution_id": parent_execution_id, "stage": stage}
        )
        return self.model_copy(update={"context": child_context})

    def evidence_envelope(self) -> FlowEvidenceEnvelope:
        """Return only bounded identity metadata; raw items and metadata are excluded."""
        return FlowEvidenceEnvelope(
            contract_version=self.contract_version,
            request_id=self.context.request_id,
            correlation_id=self.context.correlation_id,
            direction=self.context.direction,
            stage=self.context.stage,
            parent_execution_id=self.context.parent_execution_id,
            item_count=len(self.items),
        )


class FlowContractError(ValueError):
    """Stable, payload-free diagnostic for cross-contract validation failures."""

    def __init__(
        self,
        code: str,
        *,
        flow_id: str | None = None,
        node_id: str | None = None,
    ) -> None:
        self.code = code
        self.flow_id = flow_id
        self.node_id = node_id
        parts = [code]
        if flow_id is not None:
            parts.append(f"flow_id={flow_id}")
        if node_id is not None:
            parts.append(f"node_id={node_id}")
        super().__init__(": ".join(parts))


class FlowContractRegistry:
    """Validate and resolve an immutable set of Capability and Flow contracts."""

    def __init__(
        self,
        *,
        capabilities: tuple[CapabilityDescriptor, ...],
        flows: tuple[FlowDefinition, ...],
        max_depth: int = DEFAULT_MAX_FLOW_DEPTH,
        max_nodes: int = DEFAULT_MAX_EXPANDED_NODES,
    ) -> None:
        self._capabilities = self._index_capabilities(capabilities)
        self._flows = self._index_flows(flows)
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self._validate_bindings()
        self._validate_graphs()

    @staticmethod
    def _index_capabilities(
        capabilities: tuple[CapabilityDescriptor, ...],
    ) -> dict[str, CapabilityDescriptor]:
        indexed: dict[str, CapabilityDescriptor] = {}
        for capability in capabilities:
            if capability.capability_id in indexed:
                raise FlowContractError("duplicate_capability_id")
            indexed[capability.capability_id] = capability
        return indexed

    @staticmethod
    def _index_flows(
        flows: tuple[FlowDefinition, ...],
    ) -> dict[tuple[str, str], FlowDefinition]:
        indexed: dict[tuple[str, str], FlowDefinition] = {}
        for flow in flows:
            key = (flow.flow_id, flow.version)
            if key in indexed:
                raise FlowContractError("duplicate_flow_version", flow_id=flow.flow_id)
            indexed[key] = flow
        return indexed

    def resolve_capability(
        self, node: CapabilityNodeDefinition
    ) -> CapabilityDescriptor:
        try:
            return self._capabilities[node.capability_id]
        except KeyError as exc:
            raise FlowContractError(
                "capability_reference_not_found", node_id=node.node_id
            ) from exc

    def resolve_flow(self, node: FlowNodeDefinition) -> FlowDefinition:
        try:
            return self._flows[(node.flow_id, node.flow_version)]
        except KeyError as exc:
            raise FlowContractError(
                "flow_reference_not_found",
                flow_id=node.flow_id,
                node_id=node.node_id,
            ) from exc

    def get_flow(self, flow_id: str, version: str) -> FlowDefinition:
        """Return one exact Flow definition or a stable missing-reference error."""
        try:
            return self._flows[(flow_id, version)]
        except KeyError as exc:
            raise FlowContractError("flow_reference_not_found", flow_id=flow_id) from exc

    def _validate_bindings(self) -> None:
        for flow in self._flows.values():
            for node in flow.nodes:
                if isinstance(node, CapabilityNodeDefinition):
                    capability = self.resolve_capability(node)
                    target_input_schema = capability.input_schema
                    target_output_schema = capability.output_schema
                else:
                    nested_flow = self.resolve_flow(node)
                    target_input_schema = nested_flow.input_schema
                    target_output_schema = nested_flow.output_schema
                if (
                    node.input_schema != target_input_schema
                    or node.output_schema != target_output_schema
                ):
                    code = (
                        "capability_schema_mismatch"
                        if isinstance(node, CapabilityNodeDefinition)
                        else "flow_schema_mismatch"
                    )
                    raise FlowContractError(
                        code,
                        flow_id=flow.flow_id,
                        node_id=node.node_id,
                    )

    def _validate_graphs(self) -> None:
        for flow in self._flows.values():
            self._walk_flow(flow, depth=1, active=(), expanded_nodes=0)

    def _walk_flow(
        self,
        flow: FlowDefinition,
        *,
        depth: int,
        active: tuple[tuple[str, str], ...],
        expanded_nodes: int,
    ) -> int:
        key = (flow.flow_id, flow.version)
        if key in active:
            raise FlowContractError("flow_cycle", flow_id=flow.flow_id)
        if depth > self._max_depth:
            raise FlowContractError("flow_depth_exceeded", flow_id=flow.flow_id)

        total = expanded_nodes + len(flow.nodes)
        if total > self._max_nodes:
            raise FlowContractError("flow_node_limit_exceeded", flow_id=flow.flow_id)
        next_active = (*active, key)
        for node in flow.nodes:
            if isinstance(node, FlowNodeDefinition):
                total = self._walk_flow(
                    self.resolve_flow(node),
                    depth=depth + 1,
                    active=next_active,
                    expanded_nodes=total,
                )
        return total
