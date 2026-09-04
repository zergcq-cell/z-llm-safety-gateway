"""Per-policy Flow runtime bundle and Detector lifecycle contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from z_llm_safety_gateway.config.models import (
    CapabilityBindingConfig,
    CircuitBreakerConfig,
    FlowRuntimeConfig,
    TenantPolicyConfig,
)
from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.status import DetectorState
from z_llm_safety_gateway.flow.contracts import FlowDefinition
from z_llm_safety_gateway.flow.policy import (
    NodePolicyConfig,
    PolicyDefaults,
    PolicySource,
    ResolvedNodePolicy,
    resolve_node_policy,
)
from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.tenancy.runtime import (
    TenantRuntimeCompilationError,
    TenantRuntimeCompiler,
)


class ConfiguredDetector(Detector):
    """Detector whose private word list is supplied only at initialization."""

    name = "keyword"
    category = "test"
    description = "configured detector"
    version = "1.0.0"

    def __init__(self, *, healthy: bool = True, fail_initialize: bool = False) -> None:
        self.healthy = healthy
        self.fail_initialize = fail_initialize
        self.words: tuple[str, ...] = ()
        self.initialize_calls = 0
        self.shutdown_calls = 0

    async def initialize(self, config: dict[str, Any]) -> None:
        self.initialize_calls += 1
        if self.fail_initialize:
            raise RuntimeError("private-initialization-detail")
        self.words = tuple(config["words"])

    async def health_check(self) -> bool:
        return self.healthy

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        del context
        confidence = 0.6 if any(word in content for word in self.words) else 0.0
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=confidence,
            risk_level="medium" if confidence else "low",
            message="matched" if confidence else "clear",
        )

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


def _flow(flow_id: str, *, required: bool = False) -> FlowDefinition:
    return FlowDefinition.model_validate(
        {
            "contract_version": "1.0",
            "flow_id": flow_id,
            "version": "1.0.0",
            "input_schema": "safety.text.v1",
            "output_schema": "safety.detector-results.v1",
            "reducer_capability_id": "detector-result-reducer",
            "nodes": [
                {
                    "contract_version": "1.0",
                    "kind": "capability",
                    "node_id": "keyword-check",
                    "capability_id": "detector.keyword",
                    "input_schema": "safety.text.v1",
                    "output_schema": "safety.detector-result.v1",
                    "policy": {
                        "availability": {
                            "required": required,
                            "on_unavailable": "fail_closed" if required else "fail_open",
                            "on_circuit_open": "fail_closed" if required else "fail_open",
                        }
                    },
                }
            ],
        }
    )


def _resolved(
    flows: tuple[FlowDefinition, ...],
) -> Mapping[tuple[str, str, str], ResolvedNodePolicy]:
    defaults = PolicyDefaults()
    return {
        (flow.flow_id, flow.version, node.node_id): resolve_node_policy(
            NodePolicyConfig.model_validate(dict(node.policy)),
            defaults=defaults,
            source=PolicySource.EXPLICIT,
            flow_id=flow.flow_id,
            node_id=node.node_id,
        )
        for flow in flows
        for node in flow.nodes
    }


def _policy(
    policy_id: str,
    flow_id: str,
    *,
    word: str,
    escalate: bool,
) -> TenantPolicyConfig:
    result_policy: dict[str, Any] = {}
    if escalate:
        result_policy["flag_escalation"] = {
            "enabled": True,
            "rule": "count >= 1",
            "action": "block",
        }
    return TenantPolicyConfig.model_validate(
        {
            "id": policy_id,
            "input_flow": {"flow_id": flow_id, "version": "1.0.0"},
            "output_flow": None,
            "capabilities": [
                {
                    "capability_id": "detector.keyword",
                    "detector_name": "keyword",
                    "config": {
                        "words": [word],
                        "flag_threshold": 0.5,
                        "block_threshold": 0.9,
                    },
                }
            ],
            "result_policy": result_policy,
            "routing": {
                "models_provider": "local",
                "rules": [{"pattern": "*", "provider": "local"}],
            },
        }
    )


@pytest.mark.asyncio
async def test_policy_bundles_isolate_flow_binding_reducer_and_status() -> None:
    """TC-DDF-008/009/011/012: compiled policy state never crosses bundles."""
    flows = (_flow("strict-input"), _flow("research-input"))
    created: list[ConfiguredDetector] = []

    def detector_factory(binding: CapabilityBindingConfig) -> ConfiguredDetector:
        assert binding.detector_name == "keyword"
        detector = ConfiguredDetector()
        created.append(detector)
        return detector

    compiler = TenantRuntimeCompiler(
        flows=flows,
        resolved_policies=_resolved(flows),
        runtime=FlowRuntimeConfig(),
        detector_factory=detector_factory,
    )
    strict, research = await compiler.compile(
        (
            _policy("strict", "strict-input", word="alpha-private", escalate=False),
            _policy("research", "research-input", word="beta-private", escalate=True),
        )
    )

    assert strict.engine is not research.engine
    assert strict.input_flow_identity == ("strict-input", "1.0.0")
    assert research.input_flow_identity == ("research-input", "1.0.0")
    assert created[0] is not created[1]
    assert created[0].words == ("alpha-private",)
    assert created[1].words == ("beta-private",)
    assert strict.status_registry is not research.status_registry
    assert strict.status_registry.get("input", "keyword").state is DetectorState.HEALTHY
    assert research.status_registry.get("input", "keyword").state is DetectorState.HEALTHY

    content = "alpha-private and beta-private"
    contexts = [
        DetectionContext(
            direction="input",
            request_id="req-1",
            metadata={"content": content},
        )
    ]
    strict_result = await strict.engine.run(
        list(strict.input_detectors), contexts, dict(strict.input_detector_configs)
    )
    research_result = await research.engine.run(
        list(research.input_detectors), contexts, dict(research.input_detector_configs)
    )
    assert strict_result.final_action == "flag"
    assert research_result.final_action == "block"
    assert strict_result.flow_evidence is not None
    assert strict_result.flow_evidence.flow_id == "strict-input"
    assert research_result.flow_evidence is not None
    assert research_result.flow_evidence.flow_id == "research-input"
    assert "alpha-private" not in repr(strict)
    assert "beta-private" not in repr(research)

    await compiler.shutdown((strict, research))
    assert [detector.shutdown_calls for detector in created] == [1, 1]


@pytest.mark.asyncio
async def test_required_failure_rejects_all_bundles_and_cleans_up() -> None:
    """TC-DDF-011: any required policy Detector failure blocks readiness."""
    healthy_flow = _flow("healthy-input")
    required_flow = _flow("required-input", required=True)
    created: list[ConfiguredDetector] = []

    def detector_factory(binding: CapabilityBindingConfig) -> ConfiguredDetector:
        detector = ConfiguredDetector(fail_initialize=binding.config["words"] == ["fail"])
        created.append(detector)
        return detector

    compiler = TenantRuntimeCompiler(
        flows=(healthy_flow, required_flow),
        resolved_policies=_resolved((healthy_flow, required_flow)),
        runtime=FlowRuntimeConfig(),
        detector_factory=detector_factory,
    )

    with pytest.raises(TenantRuntimeCompilationError) as exc_info:
        await compiler.compile(
            (
                _policy("healthy", "healthy-input", word="ok", escalate=False),
                _policy("required", "required-input", word="fail", escalate=False),
            )
        )

    assert exc_info.value.code == "tenant_required_detector_unavailable"
    assert exc_info.value.policy_id == "required"
    assert "private-initialization-detail" not in str(exc_info.value)
    assert "fail" not in str(exc_info.value)
    assert created[0].shutdown_calls == 1
    assert created[1].shutdown_calls == 1


@pytest.mark.asyncio
async def test_bundle_deep_freezes_nested_config_and_builds_private_breaker() -> None:
    """TC-DDF-009/011: nested config and circuit state remain policy-private."""
    flow = _flow("private-input")
    policy = _policy("private", "private-input", word="private", escalate=False)
    binding = policy.capabilities[0].model_copy(
        update={
            "circuit_breaker": CircuitBreakerConfig(
                enabled=True,
                failure_threshold=2,
                recovery_timeout="1s",
                fallback_action="fail_closed",
            )
        }
    )
    policy = policy.model_copy(update={"capabilities": (binding,)})
    compiler = TenantRuntimeCompiler(
        flows=(flow,),
        resolved_policies=_resolved((flow,)),
        runtime=FlowRuntimeConfig(),
        detector_factory=lambda _: ConfiguredDetector(),
    )

    bundle = (await compiler.compile((policy,)))[0]
    config = bundle.input_detector_configs["keyword"]

    assert config["circuit_breaker"] is not None
    with pytest.raises(TypeError):
        config["words"][0] = "mutated"
    await compiler.shutdown((bundle,))


@pytest.mark.asyncio
async def test_post_initialize_identity_mismatch_is_sanitized_and_cleaned_up() -> None:
    """TC-DDF-009: runtime identity is verified after plugin initialization."""
    flow = _flow("identity-input")

    class RenamingDetector(ConfiguredDetector):
        async def initialize(self, config: dict[str, Any]) -> None:
            await super().initialize(config)
            self.name = "unexpected-runtime-name"

    detector = RenamingDetector()
    compiler = TenantRuntimeCompiler(
        flows=(flow,),
        resolved_policies=_resolved((flow,)),
        runtime=FlowRuntimeConfig(),
        detector_factory=lambda _: detector,
    )

    with pytest.raises(TenantRuntimeCompilationError) as exc_info:
        await compiler.compile(
            (_policy("identity", "identity-input", word="private", escalate=False),)
        )

    assert exc_info.value.code == "tenant_detector_identity_mismatch"
    assert "unexpected-runtime-name" not in str(exc_info.value)
    assert detector.shutdown_calls == 1


@pytest.mark.asyncio
async def test_policy_registry_emits_lifecycle_transitions() -> None:
    """TC-DDF-011: tenant detector decisions retain lifecycle evidence hooks."""
    flow = _flow("audited-input")
    transitions: list[tuple[str, DetectorState, DetectorState]] = []
    compiler = TenantRuntimeCompiler(
        flows=(flow,),
        resolved_policies=_resolved((flow,)),
        runtime=FlowRuntimeConfig(),
        detector_factory=lambda _: ConfiguredDetector(),
        on_status_transition=lambda policy_id, old, new: transitions.append(
            (policy_id, old.state, new.state)
        ),
    )

    bundle = (
        await compiler.compile(
            (_policy("audited", "audited-input", word="private", escalate=False),)
        )
    )[0]

    assert (
        "audited",
        DetectorState.INITIALIZING,
        DetectorState.HEALTHY,
    ) in transitions
    await compiler.shutdown((bundle,))
