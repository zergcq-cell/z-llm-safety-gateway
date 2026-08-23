"""Deterministic compilation of legacy detector configuration into default Flows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from z_llm_safety_gateway.config.models import (
    DetectorConfig,
    DetectorsConfig,
    GatewayConfig,
)
from z_llm_safety_gateway.flow.contracts import (
    CapabilityNodeDefinition,
    FlowDefinition,
)
from z_llm_safety_gateway.flow.policy import (
    AvailabilityPolicyConfig,
    DegradationPolicyConfig,
    FailurePolicyConfig,
    FallbackAction,
    NodePolicyConfig,
    PolicyDefaults,
    PolicySource,
    ResolvedNodePolicy,
    ResolvedPolicySources,
    StopPolicyConfig,
    TimeoutPolicyConfig,
    resolve_node_policy,
)

LEGACY_INPUT_FLOW_ID = "legacy-input-detector-flow"
LEGACY_OUTPUT_FLOW_ID = "legacy-output-detector-flow"


def _duration_seconds(value: str) -> float:
    normalized = value.strip()
    if normalized.endswith("ms"):
        return float(normalized[:-2]) / 1000.0
    if normalized.endswith("s"):
        return float(normalized[:-1])
    return float(normalized)


@dataclass(frozen=True, slots=True)
class CompiledDetectorFlows:
    """Safe normalized execution contracts plus private in-memory detector config."""

    input_flow: FlowDefinition
    output_flow: FlowDefinition
    policies: Mapping[tuple[str, str, str], ResolvedNodePolicy]
    diagnostic_fingerprint: str
    output_sync_timeout_seconds: float
    _detector_configs: Mapping[tuple[str, str], DetectorConfig] = field(repr=False)

    def policy(self, flow_id: str, node_id: str) -> ResolvedNodePolicy:
        return self.policies[(flow_id, "1.0.0", node_id)]

    def detector_config(self, direction: str, name: str) -> DetectorConfig:
        return self._detector_configs[(direction, name)]


def _stop_signals(short_circuit_on: str) -> tuple[str, ...]:
    if short_circuit_on == "block_and_modify":
        return ("safety.block", "safety.modify")
    return ("safety.block",)


def _resolved_legacy_policy(
    detector: DetectorConfig,
    *,
    detector_timeout_seconds: float,
    short_circuit_on: str,
    short_circuit_explicit: bool,
) -> tuple[NodePolicyConfig, ResolvedNodePolicy]:
    timeout_seconds = (
        _duration_seconds(detector.timeout)
        if detector.timeout is not None
        else detector_timeout_seconds
    )
    circuit_action = (
        detector.circuit_breaker.fallback_action
        if detector.circuit_breaker is not None
        else detector.on_error
    )
    error_action = cast(FallbackAction, detector.on_error)
    circuit_fallback = cast(FallbackAction, circuit_action)
    config = NodePolicyConfig(
        timeout=TimeoutPolicyConfig(seconds=timeout_seconds, action=error_action),
        failure=FailurePolicyConfig(action=error_action),
        availability=AvailabilityPolicyConfig(
            required=detector.required,
            on_unavailable=error_action,
            on_circuit_open=circuit_fallback,
        ),
        degradation=DegradationPolicyConfig(
            allowed=True,
            emit_evidence=True,
            emit_metrics=True,
        ),
        stop=StopPolicyConfig(signals=_stop_signals(short_circuit_on)),
    )
    resolved = resolve_node_policy(
        config,
        defaults=PolicyDefaults(),
        source=PolicySource.LEGACY,
    )
    fields_set = detector.model_fields_set
    resolved = resolved.model_copy(
        update={
            "sources": ResolvedPolicySources(
                timeout=(
                    PolicySource.LEGACY
                    if detector.timeout is not None
                    else PolicySource.LEGACY_DEFAULT
                ),
                failure=(
                    PolicySource.LEGACY
                    if "on_error" in fields_set
                    else PolicySource.LEGACY_DEFAULT
                ),
                availability=(
                    PolicySource.LEGACY
                    if fields_set & {"required", "on_error", "circuit_breaker"}
                    else PolicySource.LEGACY_DEFAULT
                ),
                degradation=PolicySource.LEGACY_DEFAULT,
                stop=(
                    PolicySource.LEGACY
                    if short_circuit_explicit
                    else PolicySource.LEGACY_DEFAULT
                ),
            )
        }
    )
    return config, resolved


def _compile_direction(
    direction: str,
    flow_id: str,
    detectors: list[DetectorConfig],
    *,
    gateway_config: GatewayConfig,
) -> tuple[
    FlowDefinition,
    dict[tuple[str, str, str], ResolvedNodePolicy],
    dict[tuple[str, str], DetectorConfig],
]:
    nodes: list[CapabilityNodeDefinition] = []
    policies: dict[tuple[str, str, str], ResolvedNodePolicy] = {}
    private_configs: dict[tuple[str, str], DetectorConfig] = {}
    for detector in detectors:
        if not detector.enabled:
            continue
        node_id = f"{direction}-{detector.name}"
        policy_config, resolved = _resolved_legacy_policy(
            detector,
            detector_timeout_seconds=gateway_config.security.timeout.detector_seconds,
            short_circuit_on=gateway_config.pipeline.short_circuit_on,
            short_circuit_explicit=(
                "short_circuit_on" in gateway_config.pipeline.model_fields_set
            ),
        )
        nodes.append(
            CapabilityNodeDefinition(
                contract_version="1.0",
                node_id=node_id,
                capability_id=f"detector.{detector.name}",
                input_schema="safety.text.v1",
                output_schema="safety.detector-result.v1",
                priority=detector.priority,
                policy=policy_config.model_dump(mode="json"),
            )
        )
        policies[(flow_id, "1.0.0", node_id)] = resolved
        private_configs[(direction, detector.name)] = detector

    return (
        FlowDefinition(
            contract_version="1.0",
            flow_id=flow_id,
            version="1.0.0",
            input_schema="safety.text.v1",
            output_schema="safety.detector-result.v1",
            nodes=tuple(nodes),
            reducer_capability_id="detector-result-reducer",
        ),
        policies,
        private_configs,
    )


def _flow_fingerprint_payload(flow: FlowDefinition) -> dict[str, object]:
    payload = flow.model_dump(mode="json", exclude={"nodes"})
    payload["nodes"] = [
        {
            **node.model_dump(mode="json", exclude={"policy"}),
            "policy": dict(node.policy),
        }
        for node in flow.nodes
    ]
    return payload


def compile_legacy_detector_flows(config: GatewayConfig) -> CompiledDetectorFlows:
    """Compile existing pipeline.detectors into two deterministic default Flows."""
    detectors = config.pipeline.detectors
    if not isinstance(detectors, DetectorsConfig):
        raise TypeError("legacy_detector_config_not_normalized")

    input_flow, input_policies, input_configs = _compile_direction(
        "input",
        LEGACY_INPUT_FLOW_ID,
        detectors.input,
        gateway_config=config,
    )
    output_flow, output_policies, output_configs = _compile_direction(
        "output",
        LEGACY_OUTPUT_FLOW_ID,
        detectors.output,
        gateway_config=config,
    )
    policies = {**input_policies, **output_policies}
    fingerprint_payload = {
        "flows": [
            _flow_fingerprint_payload(input_flow),
            _flow_fingerprint_payload(output_flow),
        ],
        "policies": {
            ":".join(key): value.model_dump(mode="json")
            for key, value in sorted(policies.items())
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return CompiledDetectorFlows(
        input_flow=input_flow,
        output_flow=output_flow,
        policies=MappingProxyType(policies),
        diagnostic_fingerprint=fingerprint,
        output_sync_timeout_seconds=_duration_seconds(config.pipeline.sync_timeout),
        _detector_configs=MappingProxyType({**input_configs, **output_configs}),
    )
