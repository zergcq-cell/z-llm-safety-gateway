"""Detector framework compatibility through the Flow Capability coordinator."""

from __future__ import annotations

import inspect
from typing import Any

from z_llm_safety_gateway_sdk import Detector as SdkDetector

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.registry import DetectorRegistry
from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry
from z_llm_safety_gateway.flow.detector_adapter import DetectorCapabilityCoordinator
from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.plugins.grpc.proto.detector.v1 import detector_pb2


class LifecycleDetector(Detector):
    name = "lifecycle"
    category = "test"
    description = "Lifecycle test detector"
    version = "1"

    def __init__(self, name: str, kind: str) -> None:
        self.name = name
        self.kind = kind
        self.initialize_calls = 0
        self.health_calls = 0
        self.shutdown_calls = 0

    async def initialize(self, config: dict[str, Any]) -> None:
        del config
        self.initialize_calls += 1

    async def health_check(self) -> bool:
        self.health_calls += 1
        return True

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        del content, context
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0,
            risk_level="low",
            message="ok",
        )

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


async def test_tc_df_701() -> None:
    """TC-DF-701: four Detector kinds share one adapter/lifecycle/status path."""
    status_registry = DetectorStatusRegistry()
    coordinator = DetectorCapabilityCoordinator(status_registry)
    detectors = tuple(
        LifecycleDetector(kind, kind)
        for kind in ("builtin", "ml", "entry_point", "grpc")
    )
    for detector in detectors:
        coordinator.register(
            direction="input",
            detector=detector,
            config={},
            detector_type=detector.kind,
        )

    await coordinator.initialize_all()
    snapshot = coordinator.snapshot()

    assert [state.name for state in snapshot.states] == [
        "builtin",
        "entry_point",
        "grpc",
        "ml",
    ]
    assert all(detector.initialize_calls == 1 for detector in detectors)
    assert all(detector.health_calls == 1 for detector in detectors)
    assert all(state.state is DetectorState.HEALTHY for state in snapshot.states)
    assert all(snapshot.adapter("input", state.name) for state in snapshot.states)

    await coordinator.shutdown_all()
    assert all(detector.shutdown_calls == 1 for detector in detectors)


async def test_tc_df_702() -> None:
    """TC-DF-702: immutable snapshots remain request-stable and application-scoped."""
    first_status = DetectorStatusRegistry()
    first = DetectorCapabilityCoordinator(first_status)
    detector = LifecycleDetector("shared-name", "builtin")
    first.register(direction="input", detector=detector, config={})
    await first.initialize_all()
    request_snapshot = first.snapshot()

    first_status.transition(
        "input",
        "shared-name",
        DetectorState.UNAVAILABLE,
    )
    later_snapshot = first.snapshot()

    assert request_snapshot.state("input", "shared-name").state is DetectorState.HEALTHY
    assert later_snapshot.state("input", "shared-name").state is DetectorState.UNAVAILABLE

    second = DetectorCapabilityCoordinator(DetectorStatusRegistry())
    isolated = LifecycleDetector("shared-name", "grpc")
    second.register(direction="input", detector=isolated, config={})
    await second.initialize_all()
    assert second.snapshot().state("input", "shared-name").state is DetectorState.HEALTHY
    assert first.snapshot().state("input", "shared-name").state is DetectorState.UNAVAILABLE


def test_tc_df_703() -> None:
    """TC-DF-703: SDK, entry-point group, and gRPC v1 contracts remain unchanged."""
    assert inspect.signature(DetectorRegistry.register_from_entry_points).parameters[
        "group"
    ].default == "z_llm_safety_gateway.detectors"
    assert inspect.signature(SdkDetector.detect).parameters.keys() == {
        "self",
        "content",
        "context",
    }
    service = detector_pb2.DESCRIPTOR.services_by_name["DetectorService"]
    assert service.full_name == "z_llm_safety_gateway.detector.v1.DetectorService"
    assert {method.name for method in service.methods} == {
        "Initialize",
        "Detect",
        "HealthCheck",
        "Shutdown",
    }
