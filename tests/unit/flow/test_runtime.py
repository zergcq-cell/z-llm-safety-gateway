"""Generic Flow Runtime scheduling, nesting, stop, and cancellation tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

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
from z_llm_safety_gateway.flow.evidence import FlowStatus, NodeStatus
from z_llm_safety_gateway.flow.policy import (
    FailureKind,
    NodePolicyConfig,
    PolicyDefaults,
    StopPolicyConfig,
    TimeoutPolicyConfig,
    resolve_node_policy,
)
from z_llm_safety_gateway.flow.runtime import (
    CapabilityInvocationError,
    CapabilityResult,
    FlowRuntime,
    OrderedResultReducer,
)
from z_llm_safety_gateway.tenancy.observation import (
    ObservationScope,
    TenantObservationContext,
)


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        contract_version="1.0",
        capability_id=capability_id,
        implementation_version="test-1",
        input_schema="safety.text.v1",
        output_schema="safety.signal.v1",
    )


def _node(node_id: str, capability_id: str, priority: int = 0) -> CapabilityNodeDefinition:
    return CapabilityNodeDefinition(
        contract_version="1.0",
        node_id=node_id,
        capability_id=capability_id,
        input_schema="safety.text.v1",
        output_schema="safety.signal.v1",
        priority=priority,
    )


def _flow(
    flow_id: str,
    *nodes: CapabilityNodeDefinition | FlowNodeDefinition,
) -> FlowDefinition:
    return FlowDefinition(
        contract_version="1.0",
        flow_id=flow_id,
        version="1.0.0",
        input_schema="safety.text.v1",
        output_schema="safety.signal.v1",
        nodes=nodes,
    )


def _input(*contents: str) -> FlowInput:
    return FlowInput(
        contract_version="1.0",
        items=tuple(
            FlowItem(item_id=f"item-{index}", content=content)
            for index, content in enumerate(contents)
        ),
        context=FlowContext(
            request_id="request-1",
            correlation_id="correlation-1",
            direction="input",
            stage="input",
        ),
    )


def _policy(*, timeout: float = 1.0, stop: tuple[str, ...] = ("safety.block",)) -> Any:
    return resolve_node_policy(
        NodePolicyConfig(
            timeout=TimeoutPolicyConfig(seconds=timeout, action="fail_open"),
            stop=StopPolicyConfig(signals=stop),
        ),
        defaults=PolicyDefaults(),
    )


def _policies(flow: FlowDefinition, **overrides: Any) -> dict[tuple[str, str, str], Any]:
    return {
        (flow.flow_id, flow.version, node.node_id): overrides.get(node.node_id, _policy())
        for node in flow.nodes
    }


@dataclass
class ConcurrencyTracker:
    release: asyncio.Event = field(default_factory=asyncio.Event)
    two_started: asyncio.Event = field(default_factory=asyncio.Event)
    active: int = 0
    max_active: int = 0
    started: int = 0


class TrackedCapability:
    def __init__(self, descriptor: CapabilityDescriptor, tracker: ConcurrencyTracker) -> None:
        self.descriptor = descriptor
        self._tracker = tracker

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        del context
        self._tracker.active += 1
        self._tracker.started += 1
        self._tracker.max_active = max(self._tracker.max_active, self._tracker.active)
        if self._tracker.started >= 2:
            self._tracker.two_started.set()
        try:
            await self._tracker.release.wait()
            return CapabilityResult(output=f"{self.descriptor.capability_id}:{item.item_id}")
        finally:
            self._tracker.active -= 1


class ImmediateCapability:
    def __init__(
        self,
        descriptor: CapabilityDescriptor,
        *,
        signals: tuple[str, ...] = (),
    ) -> None:
        self.descriptor = descriptor
        self.signals = signals
        self.calls = 0

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        del context
        self.calls += 1
        return CapabilityResult(output=item.content, signals=self.signals)


class BlockingCapability:
    def __init__(self, descriptor: CapabilityDescriptor) -> None:
        self.descriptor = descriptor
        self.started = asyncio.Event()
        self.cleaned = asyncio.Event()

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        del item, context
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.cleaned.set()


class BlockingReducer:
    async def reduce(self, flow: FlowDefinition, results: Any) -> CapabilityResult:
        del flow, results
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


class CircuitOpenCapability:
    def __init__(self, descriptor: CapabilityDescriptor) -> None:
        self.descriptor = descriptor

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
        del item, context
        raise CapabilityInvocationError(FailureKind.CIRCUIT_OPEN)


async def test_tc_fr_001() -> None:
    """TC-FR-001: calls are lazily bounded and results retain definition/item order."""
    tracker = ConcurrencyTracker()
    descriptors = tuple(_descriptor(f"capability.{index}") for index in range(3))
    nodes = tuple(
        _node(f"node-{index}", item.capability_id)
        for index, item in enumerate(descriptors)
    )
    flow = _flow("bounded-flow", *nodes)
    registry = FlowContractRegistry(capabilities=descriptors, flows=(flow,))
    capabilities = {
        item.capability_id: TrackedCapability(item, tracker) for item in descriptors
    }
    runtime = FlowRuntime(
        registry=registry,
        capabilities=capabilities,
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
        max_concurrency=2,
    )

    execution = asyncio.create_task(runtime.execute(flow, _input("a", "b", "c", "d")))
    await asyncio.wait_for(tracker.two_started.wait(), timeout=1)
    assert tracker.active == 2
    assert tracker.started == 2
    tracker.release.set()
    result = await execution

    assert tracker.max_active == 2
    assert [item.node_id for item in result.node_results] == [
        node.node_id for node in nodes for _ in range(4)
    ]
    assert [item.item_index for item in result.node_results] == list(range(4)) * 3
    assert runtime.pending_task_count == 0


async def test_runtime_passes_explicit_tenant_context_to_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-TOB-001: root Flow observation uses its explicit trusted context."""
    from z_llm_safety_gateway.observability import flow as flow_observability

    descriptor = _descriptor("capability.observe")
    flow = _flow("observed-flow", _node("observe", descriptor.capability_id))
    runtime = FlowRuntime(
        registry=FlowContractRegistry(capabilities=(descriptor,), flows=(flow,)),
        capabilities={descriptor.capability_id: ImmediateCapability(descriptor)},
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
    )
    captured: list[Any] = []

    def observe(*args: Any, **kwargs: Any) -> Any:
        captured.append(kwargs["tenant_context"])
        return args[0]

    monkeypatch.setattr(flow_observability, "observe_flow_evidence", observe)
    observation = TenantObservationContext(ObservationScope.TENANT, "acme", "strict")
    flow_input = _input("safe").model_copy(
        update={
            "context": _input("safe").context.model_copy(
                update={"tenant_observation_context": observation}
            )
        }
    )

    await runtime.execute(flow, flow_input)

    assert captured == [observation]


async def test_tc_fr_002() -> None:
    """TC-FR-002: empty Nodes or empty items complete and still invoke the reducer."""
    descriptor = _descriptor("capability.empty")
    capability = ImmediateCapability(descriptor)
    empty_flow = _flow("empty-flow")
    itemless_flow = _flow("itemless-flow", _node("unused", descriptor.capability_id))
    registry = FlowContractRegistry(
        capabilities=(descriptor,),
        flows=(empty_flow, itemless_flow),
    )
    reducer = OrderedResultReducer()
    runtime = FlowRuntime(
        registry=registry,
        capabilities={descriptor.capability_id: capability},
        policies=_policies(itemless_flow),
        reducer=reducer,
    )

    empty_result = await runtime.execute(empty_flow, _input("content"))
    itemless_result = await runtime.execute(itemless_flow, _input())

    assert empty_result.evidence.status is FlowStatus.COMPLETED
    assert itemless_result.evidence.status is FlowStatus.COMPLETED
    assert empty_result.node_results == itemless_result.node_results == ()
    assert reducer.calls == 2
    assert capability.calls == 0


async def test_tc_fr_003() -> None:
    """TC-FR-003: stop signals cancel pending calls and retain completed evidence."""
    stop_descriptor = _descriptor("capability.stop")
    slow_descriptor = _descriptor("capability.slow")
    slow = BlockingCapability(slow_descriptor)

    class CoordinatedStop(ImmediateCapability):
        async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult:
            await asyncio.wait_for(slow.started.wait(), timeout=1)
            return await super().invoke(item, context)

    stop = CoordinatedStop(stop_descriptor, signals=("safety.block",))
    flow = _flow(
        "stop-flow",
        _node("stop-node", stop_descriptor.capability_id),
        _node("slow-node", slow_descriptor.capability_id),
    )
    registry = FlowContractRegistry(
        capabilities=(stop_descriptor, slow_descriptor),
        flows=(flow,),
    )
    runtime = FlowRuntime(
        registry=registry,
        capabilities={
            stop_descriptor.capability_id: stop,
            slow_descriptor.capability_id: slow,
        },
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
        max_concurrency=2,
    )

    result = await runtime.execute(flow, _input("content"))

    assert result.evidence.status is FlowStatus.STOPPED
    assert result.node_results[0].status is NodeStatus.SUCCEEDED
    assert result.node_results[1].status is NodeStatus.CANCELLED
    assert await asyncio.wait_for(slow.cleaned.wait(), timeout=1) is True
    assert runtime.pending_task_count == 0


async def test_tc_fr_004() -> None:
    """TC-FR-004: nested Flow uses the same runtime envelope and parent-bounded deadline."""
    descriptor = _descriptor("capability.child")
    capability = ImmediateCapability(descriptor, signals=("safety.allow",))
    child = _flow("child-flow", _node("child-node", descriptor.capability_id))
    nested = FlowNodeDefinition(
        contract_version="1.0",
        node_id="nested-node",
        flow_id="child-flow",
        flow_version="1.0.0",
        input_schema="safety.text.v1",
        output_schema="safety.signal.v1",
    )
    parent = _flow("parent-flow", nested)
    registry = FlowContractRegistry(capabilities=(descriptor,), flows=(parent, child))
    policies = {**_policies(parent), **_policies(child)}
    runtime = FlowRuntime(
        registry=registry,
        capabilities={descriptor.capability_id: capability},
        policies=policies,
        reducer=OrderedResultReducer(),
    )

    result = await runtime.execute(parent, _input("content"))

    assert result.node_results[0].status is NodeStatus.SUCCEEDED
    assert len(result.children) == 1
    assert result.children[0].parent_execution_id == result.evidence.execution_id
    assert result.evidence.nodes[0].child_execution_id == result.children[0].execution_id

    slow = BlockingCapability(descriptor)
    timeout_runtime = FlowRuntime(
        registry=registry,
        capabilities={descriptor.capability_id: slow},
        policies={
            **policies,
            (parent.flow_id, parent.version, nested.node_id): _policy(timeout=0.01),
        },
        reducer=OrderedResultReducer(),
    )
    timed_out = await timeout_runtime.execute(parent, _input("content"))
    assert timed_out.node_results[0].status is NodeStatus.TIMED_OUT
    assert timeout_runtime.pending_task_count == 0


async def test_tc_fr_005() -> None:
    """TC-FR-005: outer cancellation awaits cleanup and propagates CancelledError."""
    descriptor = _descriptor("capability.cancel")
    capability = BlockingCapability(descriptor)
    flow = _flow("cancel-flow", _node("cancel-node", descriptor.capability_id))
    runtime = FlowRuntime(
        registry=FlowContractRegistry(capabilities=(descriptor,), flows=(flow,)),
        capabilities={descriptor.capability_id: capability},
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
    )

    execution = asyncio.create_task(runtime.execute(flow, _input("content")))
    await asyncio.wait_for(capability.started.wait(), timeout=1)
    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution

    assert await asyncio.wait_for(capability.cleaned.wait(), timeout=1) is True
    assert runtime.pending_task_count == 0


async def test_tc_fr_006() -> None:
    """TC-FR-006: graph and deadline limits preserve completed work and leave no tasks."""
    descriptor = _descriptor("capability.limit")
    too_many_nodes = _flow(
        "too-many",
        *(_node(f"node-{index}", descriptor.capability_id) for index in range(3)),
    )
    with pytest.raises(FlowContractError) as node_error:
        FlowContractRegistry(
            capabilities=(descriptor,),
            flows=(too_many_nodes,),
            max_nodes=2,
        )
    assert node_error.value.code == "flow_node_limit_exceeded"

    immediate_descriptor = _descriptor("capability.immediate")
    slow_descriptor = _descriptor("capability.deadline")
    immediate = ImmediateCapability(immediate_descriptor)
    slow = BlockingCapability(slow_descriptor)
    flow = _flow(
        "deadline-flow",
        _node("completed-node", immediate_descriptor.capability_id),
        _node("timeout-node", slow_descriptor.capability_id),
    )
    runtime = FlowRuntime(
        registry=FlowContractRegistry(
            capabilities=(immediate_descriptor, slow_descriptor),
            flows=(flow,),
        ),
        capabilities={
            immediate_descriptor.capability_id: immediate,
            slow_descriptor.capability_id: slow,
        },
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
        max_concurrency=1,
        absolute_timeout=0.03,
    )
    result = await runtime.execute(flow, _input("content"))

    assert [item.status for item in result.node_results] == [
        NodeStatus.SUCCEEDED,
        NodeStatus.TIMED_OUT,
    ]
    assert result.evidence.status is FlowStatus.TIMED_OUT
    assert runtime.pending_task_count == 0


async def test_flow_reducer_is_bounded_by_absolute_deadline() -> None:
    flow = _flow("reducer-timeout")
    runtime = FlowRuntime(
        registry=FlowContractRegistry(capabilities=(), flows=(flow,)),
        capabilities={},
        policies={},
        reducer=BlockingReducer(),
        absolute_timeout=0.02,
    )

    with pytest.raises(RuntimeError, match="flow_reducer_timeout"):
        await asyncio.wait_for(runtime.execute(flow, _input("content")), timeout=0.1)
    assert runtime.pending_task_count == 0


async def test_typed_circuit_open_produces_skipped_degraded_evidence() -> None:
    descriptor = _descriptor("capability.circuit")
    flow = _flow("circuit-flow", _node("circuit-node", descriptor.capability_id))
    runtime = FlowRuntime(
        registry=FlowContractRegistry(capabilities=(descriptor,), flows=(flow,)),
        capabilities={descriptor.capability_id: CircuitOpenCapability(descriptor)},
        policies=_policies(flow),
        reducer=OrderedResultReducer(),
    )

    result = await runtime.execute(flow, _input("content"))

    assert result.node_results[0].status is NodeStatus.SKIPPED
    assert result.evidence.nodes[0].status is NodeStatus.SKIPPED
    assert result.evidence.nodes[0].reason_code == "circuit_open"
    assert result.evidence.nodes[0].degraded is True


async def test_nested_flow_resolves_its_declared_reducer() -> None:
    descriptor = _descriptor("capability.nested-reducer")
    capability = ImmediateCapability(descriptor)
    child = _flow("child-reducer-flow", _node("child", descriptor.capability_id))
    child = child.model_copy(update={"reducer_capability_id": "child-reducer"})
    nested = FlowNodeDefinition(
        contract_version="1.0",
        node_id="nested",
        flow_id=child.flow_id,
        flow_version=child.version,
        input_schema=child.input_schema,
        output_schema=child.output_schema,
    )
    parent = _flow("parent-reducer-flow", nested)
    parent_reducer = OrderedResultReducer()
    child_reducer = OrderedResultReducer()
    runtime = FlowRuntime(
        registry=FlowContractRegistry(
            capabilities=(descriptor,),
            flows=(parent, child),
        ),
        capabilities={descriptor.capability_id: capability},
        policies={**_policies(parent), **_policies(child)},
        reducer=parent_reducer,
        reducers={"child-reducer": child_reducer},
    )

    result = await runtime.execute(parent, _input("content"))

    assert result.evidence.status is FlowStatus.COMPLETED
    assert child_reducer.calls == 1
    assert parent_reducer.calls == 1
