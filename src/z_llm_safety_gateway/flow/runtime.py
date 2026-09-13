"""Domain-neutral, bounded Flow execution runtime."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from z_llm_safety_gateway.flow.contracts import (
    CapabilityDescriptor,
    CapabilityNodeDefinition,
    FlowContext,
    FlowContractRegistry,
    FlowDefinition,
    FlowInput,
    FlowItem,
    FlowNodeDefinition,
)
from z_llm_safety_gateway.flow.evidence import (
    DEFAULT_MAX_EVIDENCE_SIZE,
    FlowEvidence,
    FlowStatus,
    NodeEvidence,
    NodeStatus,
    SafeEvidenceSummary,
    bound_flow_evidence,
    build_node_evidence,
)
from z_llm_safety_gateway.flow.policy import (
    FailureKind,
    ResolvedNodePolicy,
    evaluate_failure,
)

MAX_RUNTIME_CONCURRENCY = 64
MAX_RUNTIME_TIMEOUT_SECONDS = 120.0
_SIGNAL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CapabilityResult(BaseModel):
    """In-memory result returned by any Capability implementation."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    output: Any = None
    signals: tuple[str, ...] = Field(default=(), max_length=32)
    evidence_summary: SafeEvidenceSummary | Mapping[str, object] | None = None

    @field_validator("signals")
    @classmethod
    def _validate_signals(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SIGNAL_PATTERN.fullmatch(value) for value in values):
            raise ValueError("invalid_capability_signal")
        return values


class CapabilityInvocationError(RuntimeError):
    """Typed, payload-free failure raised by a Capability boundary adapter."""

    def __init__(self, kind: FailureKind) -> None:
        self.kind = kind
        super().__init__(kind.value)


class RuntimeCapability(Protocol):
    descriptor: CapabilityDescriptor

    async def invoke(self, item: FlowItem, context: FlowContext) -> CapabilityResult: ...


@dataclass(frozen=True, slots=True)
class NodeExecutionResult:
    node_id: str
    definition_index: int
    item_index: int
    status: NodeStatus
    output: Any
    signals: tuple[str, ...]
    reason_code: str
    degraded: bool
    duration_ms: float
    stop_requested: bool = False
    evidence_summary: SafeEvidenceSummary | Mapping[str, object] | None = None
    child_execution_id: str | None = None


@dataclass(frozen=True, slots=True)
class FlowExecutionResult:
    output: Any
    signals: tuple[str, ...]
    node_results: tuple[NodeExecutionResult, ...]
    evidence: FlowEvidence
    children: tuple[FlowEvidence, ...] = ()


class RuntimeReducer(Protocol):
    async def reduce(
        self,
        flow: FlowDefinition,
        results: tuple[NodeExecutionResult, ...],
    ) -> CapabilityResult: ...


class OrderedResultReducer:
    """Minimal domain-neutral reducer used by core tests and empty Flows."""

    def __init__(self) -> None:
        self.calls = 0

    async def reduce(
        self,
        flow: FlowDefinition,
        results: tuple[NodeExecutionResult, ...],
    ) -> CapabilityResult:
        del flow
        self.calls += 1
        outputs = tuple(
            result.output for result in results if result.status is NodeStatus.SUCCEEDED
        )
        signals = tuple(dict.fromkeys(signal for result in results for signal in result.signals))
        return CapabilityResult(output=outputs, signals=signals[:32])


@dataclass(frozen=True, slots=True)
class _WorkItem:
    order: int
    node_index: int
    item_index: int
    node: CapabilityNodeDefinition | FlowNodeDefinition
    item: FlowItem | None


@dataclass(frozen=True, slots=True)
class _WorkOutcome:
    result: NodeExecutionResult
    children: tuple[FlowEvidence, ...] = ()


class FlowRuntime:
    """Execute Flow Nodes with bounded task creation and deterministic convergence."""

    def __init__(
        self,
        *,
        registry: FlowContractRegistry,
        capabilities: Mapping[str, RuntimeCapability],
        policies: Mapping[tuple[str, str, str], ResolvedNodePolicy],
        reducer: RuntimeReducer,
        reducers: Mapping[str, RuntimeReducer] | None = None,
        max_concurrency: int = MAX_RUNTIME_CONCURRENCY,
        absolute_timeout: float = MAX_RUNTIME_TIMEOUT_SECONDS,
        max_evidence_size: int = DEFAULT_MAX_EVIDENCE_SIZE,
    ) -> None:
        if not 1 <= max_concurrency <= MAX_RUNTIME_CONCURRENCY:
            raise ValueError("invalid_runtime_concurrency")
        if not 0 < absolute_timeout <= MAX_RUNTIME_TIMEOUT_SECONDS:
            raise ValueError("invalid_runtime_timeout")
        if max_evidence_size != DEFAULT_MAX_EVIDENCE_SIZE:
            raise ValueError("invalid_evidence_budget")
        self._registry = registry
        self._capabilities = dict(capabilities)
        self._policies = dict(policies)
        self._reducer = reducer
        self._reducers = dict(reducers or {})
        self._max_concurrency = max_concurrency
        self._absolute_timeout = absolute_timeout
        self._max_evidence_size = max_evidence_size
        self._tasks: set[asyncio.Task[_WorkOutcome]] = set()
        self._evidence_templates: dict[tuple[str, str], tuple[NodeEvidence, ...]] = {}

    @property
    def pending_task_count(self) -> int:
        return sum(not task.done() for task in self._tasks)

    async def execute(
        self,
        flow: FlowDefinition,
        flow_input: FlowInput,
        *,
        reducer: RuntimeReducer | None = None,
    ) -> FlowExecutionResult:
        """Execute one root Flow within the configured absolute deadline."""
        deadline = asyncio.get_running_loop().time() + self._absolute_timeout
        return await self._execute_flow(
            flow,
            flow_input,
            parent_execution_id=None,
            deadline=deadline,
            reducer=reducer or self._reducer,
        )

    async def _execute_flow(
        self,
        flow: FlowDefinition,
        flow_input: FlowInput,
        *,
        parent_execution_id: str | None,
        deadline: float,
        reducer: RuntimeReducer,
    ) -> FlowExecutionResult:
        from z_llm_safety_gateway.observability.tenant import bound_tenant_observation

        if flow_input.context.tenant_observation_context is None:
            return await self._execute_bound(
                flow,
                flow_input,
                parent_execution_id=parent_execution_id,
                deadline=deadline,
                reducer=reducer,
            )
        with bound_tenant_observation(flow_input.context.tenant_observation_context):
            return await self._execute_bound(
                flow,
                flow_input,
                parent_execution_id=parent_execution_id,
                deadline=deadline,
                reducer=reducer,
            )

    async def _execute_bound(
        self,
        flow: FlowDefinition,
        flow_input: FlowInput,
        *,
        parent_execution_id: str | None,
        deadline: float,
        reducer: RuntimeReducer,
    ) -> FlowExecutionResult:
        """Execute one Flow with its task-local observation projection bound."""
        started = time.perf_counter()
        execution_id = f"flow-{uuid4().hex}"
        work = self._build_work(flow, flow_input)
        results: dict[int, NodeExecutionResult] = {}
        children_by_order: dict[int, tuple[FlowEvidence, ...]] = {}
        active: dict[asyncio.Task[_WorkOutcome], _WorkItem] = {}
        next_index = 0
        stopped = False
        timed_out = False
        # Reserve a small, bounded portion of the absolute deadline for the
        # reducer so a Node cannot consume the entire Flow budget.
        reducer_reserve = min(0.01, max(0.001, self._absolute_timeout * 0.1))
        work_deadline = deadline - reducer_reserve

        def fill_active() -> None:
            nonlocal next_index
            while next_index < len(work) and len(active) < self._max_concurrency:
                item = work[next_index]
                task = asyncio.create_task(
                    self._execute_work(
                        flow,
                        flow_input,
                        item,
                        execution_id=execution_id,
                        deadline=work_deadline,
                        reducer=reducer,
                    )
                )
                active[task] = item
                self._tasks.add(task)
                next_index += 1

        fill_active()
        try:
            # Give non-blocking in-process capabilities one scheduler turn.
            # Their tasks can then be collected without allocating an
            # additional asyncio.wait waiter and event-loop turn.
            if active:
                await asyncio.sleep(0)
            while active:
                remaining = work_deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    timed_out = True
                    await self._settle_active(
                        flow,
                        active,
                        results,
                        children_by_order,
                        fallback_status=NodeStatus.TIMED_OUT,
                        fallback_reason="node_timeout",
                    )
                    break
                done = {task for task in active if task.done()}
                if not done:
                    done, _ = await asyncio.wait(
                        active,
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                if not done:
                    timed_out = True
                    await self._settle_active(
                        flow,
                        active,
                        results,
                        children_by_order,
                        fallback_status=NodeStatus.TIMED_OUT,
                        fallback_reason="node_timeout",
                    )
                    break

                for task in sorted(done, key=lambda candidate: active[candidate].order):
                    item = active.pop(task)
                    self._tasks.discard(task)
                    outcome = task.result()
                    results[item.order] = outcome.result
                    children_by_order[item.order] = outcome.children
                    policy = self._policy_for(flow, item.node)
                    matched_signal = bool(set(outcome.result.signals) & set(policy.stop.signals))
                    if matched_signal or outcome.result.stop_requested:
                        stopped = True

                if stopped:
                    await self._settle_active(
                        flow,
                        active,
                        results,
                        children_by_order,
                        fallback_status=NodeStatus.CANCELLED,
                        fallback_reason="node_cancelled",
                    )
                    break
                fill_active()
        except asyncio.CancelledError:
            await self._cancel_without_results(active)
            raise
        finally:
            for task in active:
                self._tasks.discard(task)

        fallback_status = NodeStatus.TIMED_OUT if timed_out else NodeStatus.CANCELLED
        fallback_reason = "node_timeout" if timed_out else "node_cancelled"
        for item in work[next_index:]:
            results[item.order] = self._fallback_result(
                flow,
                item,
                status=fallback_status,
                reason=fallback_reason,
            )

        ordered_results = tuple(results[index] for index in sorted(results))
        if (
            not timed_out
            and any(result.status is NodeStatus.TIMED_OUT for result in ordered_results)
            and asyncio.get_running_loop().time() >= work_deadline
        ):
            timed_out = True
        effective_reducer = self._reducers.get(flow.reducer_capability_id or "", reducer)
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise RuntimeError("flow_reducer_timeout")
        try:
            reduction = await self._invoke_reducer(
                effective_reducer,
                flow,
                ordered_results,
                timeout=remaining,
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise RuntimeError("flow_reducer_timeout") from exc
        if stopped:
            flow_status = FlowStatus.STOPPED
            flow_reason = "stop_signal"
        elif timed_out:
            flow_status = FlowStatus.TIMED_OUT
            flow_reason = "flow_timeout"
        else:
            flow_status = FlowStatus.COMPLETED
            flow_reason = "completed"

        node_evidence = self._build_node_evidence(flow, execution_id, ordered_results)
        evidence = bound_flow_evidence(
            FlowEvidence(
                contract_version="1.0",
                execution_id=execution_id,
                parent_execution_id=parent_execution_id,
                flow_id=flow.flow_id,
                flow_version=flow.version,
                direction=flow_input.context.direction,
                stage=flow_input.context.stage,
                status=flow_status,
                reason_code=flow_reason,
                duration_ms=(time.perf_counter() - started) * 1000,
                final_signals=reduction.signals,
                nodes=node_evidence,
            ),
            max_evidence_size=self._max_evidence_size,
        )
        children = tuple(
            child for order in sorted(children_by_order) for child in children_by_order[order]
        )
        from z_llm_safety_gateway.observability.flow import observe_flow_evidence

        if parent_execution_id is None:
            observe_flow_evidence(
                evidence,
                children=children,
                tenant_context=flow_input.context.tenant_observation_context,
            )
        return FlowExecutionResult(
            output=reduction.output,
            signals=reduction.signals,
            node_results=ordered_results,
            evidence=evidence,
            children=children,
        )

    @staticmethod
    async def _invoke_reducer(
        reducer: RuntimeReducer,
        flow: FlowDefinition,
        results: tuple[NodeExecutionResult, ...],
        *,
        timeout: float,
    ) -> CapabilityResult:
        """Bound one reducer call without allocating a helper Task."""
        loop = asyncio.get_running_loop()
        current = asyncio.current_task()
        if current is None:  # pragma: no cover - asyncio supplies the caller task
            raise RuntimeError("runtime_reducer_task_missing")
        timeout_fired = False

        def cancel_for_timeout() -> None:
            nonlocal timeout_fired
            timeout_fired = True
            current.cancel()

        timeout_handle = loop.call_later(timeout, cancel_for_timeout)
        try:
            reduction = await reducer.reduce(flow, results)
            if timeout_fired:
                raise asyncio.TimeoutError
            return reduction
        except asyncio.CancelledError:
            if timeout_fired:
                raise asyncio.TimeoutError from None
            raise
        finally:
            timeout_handle.cancel()

    @staticmethod
    def _build_work(flow: FlowDefinition, flow_input: FlowInput) -> tuple[_WorkItem, ...]:
        work: list[_WorkItem] = []
        for node_index, node in enumerate(flow.nodes):
            if isinstance(node, CapabilityNodeDefinition):
                for item_index, item in enumerate(flow_input.items):
                    work.append(
                        _WorkItem(
                            order=len(work),
                            node_index=node_index,
                            item_index=item_index,
                            node=node,
                            item=item,
                        )
                    )
            else:
                work.append(
                    _WorkItem(
                        order=len(work),
                        node_index=node_index,
                        item_index=0,
                        node=node,
                        item=None,
                    )
                )
        return tuple(work)

    def _policy_for(
        self,
        flow: FlowDefinition,
        node: CapabilityNodeDefinition | FlowNodeDefinition,
    ) -> ResolvedNodePolicy:
        try:
            return self._policies[(flow.flow_id, flow.version, node.node_id)]
        except KeyError as exc:
            raise RuntimeError(
                f"resolved_policy_missing: flow_id={flow.flow_id}: node_id={node.node_id}"
            ) from exc

    async def _execute_work(
        self,
        flow: FlowDefinition,
        flow_input: FlowInput,
        work: _WorkItem,
        *,
        execution_id: str,
        deadline: float,
        reducer: RuntimeReducer,
    ) -> _WorkOutcome:
        started = time.perf_counter()
        policy = self._policy_for(flow, work.node)
        timeout = max(
            0.0,
            min(policy.timeout.seconds, deadline - asyncio.get_running_loop().time()),
        )
        if timeout <= 0:
            return _WorkOutcome(
                self._failure_result(
                    work,
                    policy,
                    FailureKind.TIMEOUT,
                    NodeStatus.TIMED_OUT,
                    started,
                )
            )

        try:
            if isinstance(work.node, CapabilityNodeDefinition):
                capability = self._capabilities.get(work.node.capability_id)
                if capability is None:
                    return _WorkOutcome(
                        self._failure_result(
                            work,
                            policy,
                            FailureKind.UNAVAILABLE,
                            NodeStatus.SKIPPED,
                            started,
                        )
                    )
                if work.item is None:
                    raise RuntimeError("capability_item_missing")
                result = await self._invoke_capability(
                    capability,
                    work.item,
                    flow_input.context,
                    timeout=timeout,
                )
                node_result = NodeExecutionResult(
                    node_id=work.node.node_id,
                    definition_index=work.node_index,
                    item_index=work.item_index,
                    status=NodeStatus.SUCCEEDED,
                    output=result.output,
                    signals=result.signals,
                    reason_code="completed",
                    degraded=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    evidence_summary=result.evidence_summary,
                )
                return _WorkOutcome(node_result)

            child_flow = self._registry.resolve_flow(work.node)
            child_input = flow_input.for_child(
                parent_execution_id=execution_id,
                stage="nested-flow",
            )
            child_result = await self._execute_flow(
                child_flow,
                child_input,
                parent_execution_id=execution_id,
                deadline=min(deadline, asyncio.get_running_loop().time() + timeout),
                reducer=reducer,
            )
            child_status = (
                NodeStatus.SUCCEEDED
                if child_result.evidence.status is FlowStatus.COMPLETED
                else NodeStatus.TIMED_OUT
                if child_result.evidence.status is FlowStatus.TIMED_OUT
                else NodeStatus.PARTIAL
            )
            node_result = NodeExecutionResult(
                node_id=work.node.node_id,
                definition_index=work.node_index,
                item_index=work.item_index,
                status=child_status,
                output=child_result.output,
                signals=child_result.signals,
                reason_code=(
                    "completed" if child_status is NodeStatus.SUCCEEDED else "child_flow_incomplete"
                ),
                degraded=child_status is not NodeStatus.SUCCEEDED,
                duration_ms=(time.perf_counter() - started) * 1000,
                child_execution_id=child_result.evidence.execution_id,
            )
            return _WorkOutcome(
                node_result,
                children=(child_result.evidence, *child_result.children),
            )
        except CapabilityInvocationError as exc:
            return _WorkOutcome(
                self._failure_result(
                    work,
                    policy,
                    exc.kind,
                    (
                        NodeStatus.SKIPPED
                        if exc.kind in {FailureKind.UNAVAILABLE, FailureKind.CIRCUIT_OPEN}
                        else NodeStatus.FAILED
                    ),
                    started,
                )
            )
        except (asyncio.TimeoutError, TimeoutError):
            return _WorkOutcome(
                self._failure_result(
                    work,
                    policy,
                    FailureKind.TIMEOUT,
                    NodeStatus.TIMED_OUT,
                    started,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return _WorkOutcome(
                self._failure_result(
                    work,
                    policy,
                    FailureKind.ERROR,
                    NodeStatus.FAILED,
                    started,
                )
            )

    @staticmethod
    async def _invoke_capability(
        capability: RuntimeCapability,
        item: FlowItem,
        context: FlowContext,
        *,
        timeout: float,
    ) -> CapabilityResult:
        """Apply a timeout without creating a second task for every invocation."""
        loop = asyncio.get_running_loop()
        current = asyncio.current_task()
        if current is None:  # pragma: no cover - asyncio always supplies the work task
            raise RuntimeError("runtime_work_task_missing")
        timeout_fired = False

        def cancel_for_timeout() -> None:
            nonlocal timeout_fired
            timeout_fired = True
            current.cancel()

        timeout_handle = loop.call_later(timeout, cancel_for_timeout)
        try:
            result = await capability.invoke(item, context)
            if timeout_fired:
                raise asyncio.TimeoutError
            return result
        except asyncio.CancelledError:
            if timeout_fired:
                raise asyncio.TimeoutError from None
            raise
        finally:
            timeout_handle.cancel()

    @staticmethod
    def _failure_result(
        work: _WorkItem,
        policy: ResolvedNodePolicy,
        kind: FailureKind,
        status: NodeStatus,
        started: float,
    ) -> NodeExecutionResult:
        decision = evaluate_failure(policy, kind)
        return NodeExecutionResult(
            node_id=work.node.node_id,
            definition_index=work.node_index,
            item_index=work.item_index,
            status=status,
            output=None,
            signals=(),
            reason_code=decision.reason_code,
            degraded=decision.degraded,
            duration_ms=(time.perf_counter() - started) * 1000,
            stop_requested=decision.stop_requested,
        )

    def _fallback_result(
        self,
        flow: FlowDefinition,
        work: _WorkItem,
        *,
        status: NodeStatus,
        reason: str,
    ) -> NodeExecutionResult:
        policy = self._policy_for(flow, work.node)
        stop_requested = (
            evaluate_failure(policy, FailureKind.TIMEOUT).stop_requested
            if status is NodeStatus.TIMED_OUT
            else False
        )
        return NodeExecutionResult(
            node_id=work.node.node_id,
            definition_index=work.node_index,
            item_index=work.item_index,
            status=status,
            output=None,
            signals=(),
            reason_code=reason,
            degraded=True,
            duration_ms=0.0,
            stop_requested=stop_requested,
        )

    async def _settle_active(
        self,
        flow: FlowDefinition,
        active: dict[asyncio.Task[_WorkOutcome], _WorkItem],
        results: dict[int, NodeExecutionResult],
        children_by_order: dict[int, tuple[FlowEvidence, ...]],
        *,
        fallback_status: NodeStatus,
        fallback_reason: str,
    ) -> None:
        tasks = tuple(active)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            work = active.pop(task)
            self._tasks.discard(task)
            if task.cancelled():
                results[work.order] = self._fallback_result(
                    flow,
                    work,
                    status=fallback_status,
                    reason=fallback_reason,
                )
            else:
                outcome = task.result()
                results[work.order] = outcome.result
                children_by_order[work.order] = outcome.children

    async def _cancel_without_results(
        self,
        active: dict[asyncio.Task[_WorkOutcome], _WorkItem],
    ) -> None:
        tasks = tuple(active)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for task in tasks:
            self._tasks.discard(task)
        active.clear()

    def _build_node_evidence(
        self,
        flow: FlowDefinition,
        execution_id: str,
        results: tuple[NodeExecutionResult, ...],
    ) -> tuple[NodeEvidence, ...]:
        evidence: list[NodeEvidence] = []
        templates = self._evidence_templates_for(flow)
        for node_index, _node in enumerate(flow.nodes):
            node_results = tuple(
                result for result in results if result.definition_index == node_index
            )
            if len(node_results) == 1:
                result = node_results[0]
                status = result.status
                reason = result.reason_code
                degraded = result.degraded
                item_count = 1
                succeeded_items = int(status is NodeStatus.SUCCEEDED)
                failed_items = int(
                    status
                    in {
                        NodeStatus.FAILED,
                        NodeStatus.TIMED_OUT,
                        NodeStatus.PARTIAL,
                    }
                )
                skipped_items = int(status is NodeStatus.SKIPPED)
                cancelled_items = int(status is NodeStatus.CANCELLED)
                signals = result.signals
                optional_summary = result.evidence_summary
                child_execution_id = result.child_execution_id
                duration_ms = result.duration_ms
                trusted_signals = True
            else:
                status, reason = self._aggregate_node_status(node_results)
                degraded = any(result.degraded for result in node_results)
                item_count = len(node_results)
                succeeded_items = sum(
                    result.status is NodeStatus.SUCCEEDED for result in node_results
                )
                failed_items = sum(
                    result.status in {NodeStatus.FAILED, NodeStatus.TIMED_OUT}
                    for result in node_results
                )
                skipped_items = sum(result.status is NodeStatus.SKIPPED for result in node_results)
                cancelled_items = sum(
                    result.status is NodeStatus.CANCELLED for result in node_results
                )
                signals = tuple(
                    dict.fromkeys(signal for result in node_results for signal in result.signals)
                )
                optional_summary = next(
                    (
                        result.evidence_summary
                        for result in node_results
                        if result.evidence_summary is not None
                    ),
                    None,
                )
                child_execution_id = next(
                    (
                        result.child_execution_id
                        for result in node_results
                        if result.child_execution_id is not None
                    ),
                    None,
                )
                duration_ms = sum(result.duration_ms for result in node_results)
                trusted_signals = False
            evidence.append(
                build_node_evidence(
                    base_node=templates[node_index],
                    execution_id=execution_id,
                    status=status,
                    degraded=degraded,
                    reason_code=reason,
                    duration_ms=duration_ms,
                    item_count=item_count,
                    succeeded_items=succeeded_items,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                    cancelled_items=cancelled_items,
                    signals=signals,
                    trusted_signals=trusted_signals,
                    optional_summary=optional_summary,
                    child_execution_id=child_execution_id,
                )
            )
        return tuple(evidence)

    @staticmethod
    def _aggregate_node_status(
        node_results: tuple[NodeExecutionResult, ...],
    ) -> tuple[NodeStatus, str]:
        statuses = {result.status for result in node_results}
        if not node_results or statuses == {NodeStatus.SUCCEEDED}:
            return NodeStatus.SUCCEEDED, "completed"
        status = next(iter(statuses)) if len(statuses) == 1 else NodeStatus.PARTIAL
        reason = next(
            (
                result.reason_code
                for result in node_results
                if result.status is not NodeStatus.SUCCEEDED
            ),
            "node_partial",
        )
        return status, reason

    def _evidence_templates_for(self, flow: FlowDefinition) -> tuple[NodeEvidence, ...]:
        key = (flow.flow_id, flow.version)
        cached = self._evidence_templates.get(key)
        if cached is not None:
            return cached
        templates: list[NodeEvidence] = []
        for node_index, node in enumerate(flow.nodes):
            if isinstance(node, CapabilityNodeDefinition):
                target = self._registry.resolve_capability(node)
                target_id = target.capability_id
                target_contract_version = target.contract_version
                target_implementation_version = target.implementation_version
            else:
                child = self._registry.resolve_flow(node)
                target_id = child.flow_id
                target_contract_version = child.contract_version
                target_implementation_version = child.version
            templates.append(
                build_node_evidence(
                    contract_version="1.0",
                    flow_id=flow.flow_id,
                    flow_version=flow.version,
                    execution_id="flow-template",
                    node_id=node.node_id,
                    definition_index=node_index,
                    target_id=target_id,
                    target_contract_version=target_contract_version,
                    target_implementation_version=target_implementation_version,
                    effective_policy=self._policy_for(flow, node),
                    status=NodeStatus.SUCCEEDED,
                    degraded=False,
                    reason_code="completed",
                    duration_ms=0.0,
                    item_count=0,
                    succeeded_items=0,
                    failed_items=0,
                    skipped_items=0,
                    cancelled_items=0,
                )
            )
        result = tuple(templates)
        self._evidence_templates[key] = result
        return result
