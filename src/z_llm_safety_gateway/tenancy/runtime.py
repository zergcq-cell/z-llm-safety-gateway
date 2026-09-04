"""Startup compilation of isolated per-policy Flow runtime bundles."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

import structlog

from z_llm_safety_gateway.circuit_breaker.factory import build_circuit_breaker
from z_llm_safety_gateway.config.models import (
    CapabilityBindingConfig,
    FlowRuntimeConfig,
    TenantPolicyConfig,
)
from z_llm_safety_gateway.detectors.status import (
    DetectorState,
    DetectorStatus,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.flow.contracts import (
    CapabilityNodeDefinition,
    FlowDefinition,
    FlowNodeDefinition,
)
from z_llm_safety_gateway.flow.detector_adapter import DetectorCapabilityCoordinator
from z_llm_safety_gateway.flow.policy import ResolvedNodePolicy
from z_llm_safety_gateway.pipeline.engine import PipelineEngine
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule
from z_llm_safety_gateway.tenancy.policy import FlowIdentity, TenantRuntimeBundle

DetectorFactory = Callable[[CapabilityBindingConfig], Any]
PolicyKey = tuple[str, str, str]
logger = structlog.get_logger(__name__)


class TenantRuntimeCompilationError(RuntimeError):
    """Stable, secret-free startup failure for one tenant policy bundle."""

    def __init__(self, code: str, *, policy_id: str, detector_name: str = "") -> None:
        self.code = code
        self.policy_id = policy_id
        self.detector_name = detector_name
        detail = f"{code}: policy_id={policy_id}"
        if detector_name:
            detail += f", detector_name={detector_name}"
        super().__init__(detail)


class TenantRuntimeCompiler:
    """Compile immutable policy-private engines, plugins, configs, and status."""

    def __init__(
        self,
        *,
        flows: Sequence[FlowDefinition],
        resolved_policies: Mapping[PolicyKey, ResolvedNodePolicy],
        runtime: FlowRuntimeConfig,
        detector_factory: DetectorFactory,
        on_status_transition: Callable[
            [str, DetectorStatus, DetectorStatus], None
        ]
        | None = None,
    ) -> None:
        self._flows = {(flow.flow_id, flow.version): flow for flow in flows}
        self._resolved_policies = dict(resolved_policies)
        self._runtime_options = runtime.model_dump()
        self._detector_factory = detector_factory
        self._on_status_transition = on_status_transition

    async def compile(
        self,
        policies: Sequence[TenantPolicyConfig],
    ) -> tuple[TenantRuntimeBundle, ...]:
        """Compile every declared policy or clean up and fail the whole startup."""
        bundles: list[TenantRuntimeBundle] = []
        try:
            for policy in policies:
                bundles.append(await self._compile_policy(policy))
        except BaseException:
            await self.shutdown(tuple(bundles))
            raise
        return tuple(bundles)

    async def shutdown(self, bundles: Sequence[TenantRuntimeBundle]) -> None:
        """Release every policy's private Detector instances in reverse order."""
        for bundle in reversed(bundles):
            coordinator = bundle.detector_coordinator
            if coordinator is not None:
                await coordinator.shutdown_all()

    async def _compile_policy(self, policy: TenantPolicyConfig) -> TenantRuntimeBundle:
        input_identity = _flow_identity(policy, "input")
        output_identity = _flow_identity(policy, "output")
        selected_flows = self._selected_flows(
            policy.id,
            tuple(identity for identity in (input_identity, output_identity) if identity),
        )
        selected_policies = self._selected_policies(policy.id, selected_flows)
        bindings = {binding.capability_id: binding for binding in policy.capabilities}
        direction_nodes = {
            "input": self._detector_nodes(policy.id, input_identity),
            "output": self._detector_nodes(policy.id, output_identity),
        }
        used_capabilities = {
            node.capability_id
            for nodes in direction_nodes.values()
            for node in nodes
        }
        if used_capabilities != set(bindings):
            raise TenantRuntimeCompilationError(
                "tenant_capability_binding_mismatch", policy_id=policy.id
            )

        # Compile all pure policy/runtime state before acquiring Detector resources.
        flag_escalation = _flag_escalation(policy)
        engine = PipelineEngine(
            flag_escalation=flag_escalation,
            flows=selected_flows,
            input_flow=input_identity,
            output_flow=output_identity,
            resolved_policies=selected_policies,
            runtime_options=self._runtime_options,
        )

        detector_by_capability: dict[str, Any] = {}
        try:
            for capability_id in sorted(used_capabilities):
                binding = bindings[capability_id]
                try:
                    detector = self._detector_factory(binding)
                except Exception:
                    raise TenantRuntimeCompilationError(
                        "tenant_detector_factory_error",
                        policy_id=policy.id,
                        detector_name=binding.detector_name,
                    ) from None
                if str(getattr(detector, "name", "")) != binding.detector_name:
                    await _shutdown_detector(detector)
                    raise TenantRuntimeCompilationError(
                        "tenant_detector_identity_mismatch",
                        policy_id=policy.id,
                        detector_name=binding.detector_name,
                    )
                detector_by_capability[capability_id] = detector
        except BaseException:
            for created in reversed(tuple(detector_by_capability.values())):
                await _shutdown_detector(created)
            raise

        status_registry = DetectorStatusRegistry(
            on_transition=(
                lambda old, new: self._on_status_transition(policy.id, old, new)
                if self._on_status_transition is not None
                else None
            )
        )
        coordinator = DetectorCapabilityCoordinator(status_registry)
        configs: dict[str, dict[str, dict[str, Any]]] = {"input": {}, "output": {}}
        detector_policies: dict[str, dict[str, ResolvedNodePolicy]] = {
            "input": {},
            "output": {},
        }
        try:
            for direction, nodes in direction_nodes.items():
                for node in nodes:
                    binding = bindings[node.capability_id]
                    flow_id, flow_version = self._node_flow(selected_flows, node)
                    resolved = selected_policies[
                        (flow_id, flow_version, node.node_id)
                    ]
                    detector_config = _detector_config(binding, node, resolved)
                    name = binding.detector_name
                    existing = configs[direction].get(name)
                    if existing is not None and existing != detector_config:
                        raise TenantRuntimeCompilationError(
                            "tenant_capability_lifecycle_conflict",
                            policy_id=policy.id,
                            detector_name=name,
                        )
                    if existing is not None:
                        continue
                    configs[direction][name] = detector_config
                    detector_policies[direction][name] = resolved
                    lifecycle_config = dict(binding.config)
                    lifecycle_config["timeout_seconds"] = resolved.timeout.seconds
                    coordinator.register(
                        direction=direction,  # type: ignore[arg-type]
                        detector=detector_by_capability[node.capability_id],
                        config=lifecycle_config,
                        detector_type=binding.type or "builtin",
                        required=resolved.availability.required,
                        on_error=resolved.availability.on_unavailable,
                        timeout_seconds=resolved.timeout.seconds,
                    )
            await coordinator.initialize_all()
            for capability_id, detector in detector_by_capability.items():
                binding = bindings[capability_id]
                if str(getattr(detector, "name", "")) != binding.detector_name:
                    raise TenantRuntimeCompilationError(
                        "tenant_detector_identity_mismatch",
                        policy_id=policy.id,
                        detector_name=binding.detector_name,
                    )
            required_issues = status_registry.issues(strict=True)
            if required_issues:
                issue = required_issues[0]
                raise TenantRuntimeCompilationError(
                    "tenant_required_detector_unavailable",
                    policy_id=policy.id,
                    detector_name=issue.name,
                )
        except BaseException:
            await coordinator.shutdown_all()
            raise

        detectors = {
            direction: tuple(
                detector_by_capability[f"detector.{name}"]
                for name in configs[direction]
                if status_registry.get(direction, name).state is DetectorState.HEALTHY
            )
            for direction in ("input", "output")
        }
        return TenantRuntimeBundle(
            policy_id=policy.id,
            input_flow_identity=input_identity,
            output_flow_identity=output_identity,
            routing_profile_id=policy.id,
            engine=engine,
            input_detectors=detectors["input"],
            output_detectors=detectors["output"],
            input_detector_configs=_freeze_configs(configs["input"]),
            output_detector_configs=_freeze_configs(configs["output"]),
            status_registry=status_registry,
            detector_coordinator=coordinator,
            resolved_node_policies=MappingProxyType(dict(selected_policies)),
            input_detector_policies=MappingProxyType(
                dict(detector_policies["input"])
            ),
            output_detector_policies=MappingProxyType(
                dict(detector_policies["output"])
            ),
        )

    def _selected_flows(
        self,
        policy_id: str,
        roots: tuple[FlowIdentity, ...],
    ) -> tuple[FlowDefinition, ...]:
        selected: dict[FlowIdentity, FlowDefinition] = {}

        def collect(identity: FlowIdentity) -> None:
            if identity in selected:
                return
            try:
                flow = self._flows[identity]
            except KeyError as exc:
                raise TenantRuntimeCompilationError(
                    "tenant_flow_not_found", policy_id=policy_id
                ) from exc
            selected[identity] = flow
            for node in flow.nodes:
                if isinstance(node, FlowNodeDefinition):
                    collect((node.flow_id, node.flow_version))

        for root in roots:
            collect(root)
        return tuple(selected.values())

    def _selected_policies(
        self,
        policy_id: str,
        flows: tuple[FlowDefinition, ...],
    ) -> dict[PolicyKey, ResolvedNodePolicy]:
        selected: dict[PolicyKey, ResolvedNodePolicy] = {}
        for flow in flows:
            for node in flow.nodes:
                key = (flow.flow_id, flow.version, node.node_id)
                try:
                    selected[key] = self._resolved_policies[key]
                except KeyError as exc:
                    raise TenantRuntimeCompilationError(
                        "tenant_node_policy_not_found", policy_id=policy_id
                    ) from exc
        return selected

    def _detector_nodes(
        self,
        policy_id: str,
        root: FlowIdentity | None,
    ) -> tuple[CapabilityNodeDefinition, ...]:
        if root is None:
            return ()
        nodes: list[CapabilityNodeDefinition] = []
        active: set[FlowIdentity] = set()

        def collect(identity: FlowIdentity) -> None:
            if identity in active:
                return
            active.add(identity)
            try:
                flow = self._flows[identity]
            except KeyError as exc:
                raise TenantRuntimeCompilationError(
                    "tenant_flow_not_found", policy_id=policy_id
                ) from exc
            for node in flow.nodes:
                if isinstance(node, FlowNodeDefinition):
                    collect((node.flow_id, node.flow_version))
                elif node.capability_id.startswith("detector."):
                    nodes.append(node)
                else:
                    raise TenantRuntimeCompilationError(
                        "unsupported_runtime_capability", policy_id=policy_id
                    )

        collect(root)
        return tuple(nodes)

    @staticmethod
    def _node_flow(
        flows: tuple[FlowDefinition, ...],
        selected_node: CapabilityNodeDefinition,
    ) -> tuple[str, str]:
        for flow in flows:
            if any(node is selected_node for node in flow.nodes):
                return flow.flow_id, flow.version
        raise RuntimeError("selected_node_owner_missing")


def _flow_identity(
    policy: TenantPolicyConfig,
    direction: str,
) -> FlowIdentity | None:
    reference = policy.input_flow if direction == "input" else policy.output_flow
    if reference is None:
        return None
    return reference.flow_id, reference.version


def _detector_config(
    binding: CapabilityBindingConfig,
    node: CapabilityNodeDefinition,
    policy: ResolvedNodePolicy,
) -> dict[str, Any]:
    config = dict(binding.config)
    config.update(
        {
            "priority": node.priority,
            "required": policy.availability.required,
            "on_error": policy.availability.on_unavailable,
            "timeout_seconds": policy.timeout.seconds,
        }
    )
    config.setdefault("block_threshold", 1.0)
    config.setdefault("flag_threshold", 1.0)
    if binding.circuit_breaker is not None and binding.circuit_breaker.enabled:
        config["circuit_breaker"] = build_circuit_breaker(binding.circuit_breaker)
    return config


def _flag_escalation(policy: TenantPolicyConfig) -> FlagEscalationRule | None:
    config = policy.result_policy.flag_escalation
    if config is None or not config.enabled or not config.rule:
        return None
    if config.action != "block":
        raise TenantRuntimeCompilationError(
            "unsupported_flag_escalation_action", policy_id=policy.id
        )
    try:
        return FlagEscalationRule(config.rule)
    except ValueError:
        raise TenantRuntimeCompilationError(
            "tenant_flag_escalation_invalid", policy_id=policy.id
        ) from None


def _freeze_configs(
    configs: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    return MappingProxyType(
        {
            name: MappingProxyType(
                {key: _freeze_value(value) for key, value in config.items()}
            )
            for name, config in configs.items()
        }
    )


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return value


async def _shutdown_detector(detector: Any) -> None:
    """Release a partially created plugin without masking startup failures."""
    shutdown = getattr(detector, "shutdown", None)
    if callable(shutdown):
        try:
            await asyncio.wait_for(shutdown(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning(
                "tenant_detector_cleanup_failed",
                detector_name=getattr(detector, "name", "unknown"),
                error_type="shutdown_timeout",
            )
        except Exception:
            logger.warning(
                "tenant_detector_cleanup_failed",
                detector_name=getattr(detector, "name", "unknown"),
                error_type="shutdown_error",
            )
