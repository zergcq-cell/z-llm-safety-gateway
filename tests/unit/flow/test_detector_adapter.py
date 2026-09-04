"""Detector-to-Capability adapter contract tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from z_llm_safety_gateway_sdk import (
    DetectionContext as SdkDetectionContext,
)
from z_llm_safety_gateway_sdk import (
    DetectionResult as SdkDetectionResult,
)
from z_llm_safety_gateway_sdk import (
    Detector as SdkDetector,
)

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.flow.contracts import FlowContext, FlowItem
from z_llm_safety_gateway.flow.detector_adapter import (
    DetectorCapabilityAdapter,
    DetectorCapabilityCoordinator,
)
from z_llm_safety_gateway.models import DetectionContext, DetectionResult, Modification


class RecordingDetector(Detector):
    name = "recording_detector"
    category = "test"
    description = "Records adapter input"
    version = "implementation-build-9"

    def __init__(self, result: DetectionResult | None = None) -> None:
        self.result = result or DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.1,
            risk_level="low",
            message="allowed",
        )
        self.received: tuple[str, DetectionContext] | None = None

    async def initialize(self, config: dict[str, Any]) -> None:
        del config

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        self.received = (content, context)
        return self.result


@pytest.mark.parametrize("detector_kind", ["builtin", "ml", "entry_point", "grpc"])
def test_tc_dca_001(detector_kind: str) -> None:
    """TC-DCA-001: every Detector kind exposes the same versioned descriptor schema."""
    detector = RecordingDetector()
    detector.name = f"{detector_kind}_detector"
    adapter = DetectorCapabilityAdapter(detector)
    descriptor = adapter.descriptor

    assert descriptor.contract_version == "1.0"
    assert descriptor.capability_id == f"detector.{detector_kind}_detector"
    assert descriptor.implementation_version == "implementation-build-9"
    assert descriptor.name == detector.name
    assert descriptor.category == "test"
    assert descriptor.input_schema == "safety.text.v1"
    assert descriptor.output_schema == "safety.detector-result.v1"
    assert RecordingDetector.name == "recording_detector"


@pytest.mark.parametrize(
    ("action", "expected_signal"),
    [
        ("allow", "safety.allow"),
        ("block", "safety.block"),
        ("flag", "safety.flag"),
        ("modify", "safety.modify"),
    ],
)
async def test_tc_dca_002(action: str, expected_signal: str) -> None:
    """TC-DCA-002: adapter preserves context and maps Detector results to stable signals."""
    modified = "redacted output" if action == "modify" else None
    detector = RecordingDetector(
        DetectionResult(
            detector_name="recording_detector",
            category="test",
            action=action,  # type: ignore[arg-type]
            confidence=0.83,
            risk_level="high",
            message="private detector message",
            details={"private": "details"},
            modified_content=modified,
        )
    )
    adapter = DetectorCapabilityAdapter(detector)
    item = FlowItem(
        item_id="item-3",
        content="content supplied to detector",
        metadata={"user_id": "user-7", "language": "zh", "message_index": 3},
    )
    context = FlowContext(
        request_id="request-7",
        correlation_id="correlation-7",
        direction="output",
        stage="sync-output",
    )

    result = await adapter.invoke(item, context)

    assert detector.received is not None
    received_content, received_context = detector.received
    assert received_content == item.content
    assert received_context == DetectionContext(
        direction="output",
        request_id="request-7",
        user_id="user-7",
        language="zh",
        message_index=3,
        metadata={"flow_item_id": "item-3", "correlation_id": "correlation-7"},
    )
    assert isinstance(result.output, DetectionResult)
    assert result.output.action == action
    assert result.output.modified_content == modified
    assert result.signals == (expected_signal,)
    assert result.evidence_summary is not None
    assert "message" not in result.evidence_summary
    assert "details" not in result.evidence_summary
    assert "modified_content" not in result.evidence_summary


async def test_tc_dca_003() -> None:
    """TC-DCA-003: SDK 0.1.x public models run through the adapter unchanged."""

    class SdkStyleDetector(SdkDetector):
        name = "sdk_style"
        category = "plugin"
        description = "SDK style detector"
        version = "0.1-plugin"

        async def initialize(self, config: dict[str, Any]) -> None:
            del config

        async def detect(
            self,
            content: str,
            context: SdkDetectionContext,
        ) -> SdkDetectionResult:
            assert content == "sdk content"
            assert context.request_id == "request-sdk"
            return SdkDetectionResult(
                detector_name=self.name,
                category=self.category,
                action="modify",
                confidence=0.9,
                risk_level="high",
                message="sdk message",
                modified_content="sdk redacted",
            )

    detector = SdkStyleDetector()
    await detector.initialize({})
    adapter = DetectorCapabilityAdapter(detector)
    result = await adapter.invoke(
        FlowItem(item_id="sdk-item", content="sdk content"),
        FlowContext(
            request_id="request-sdk",
            correlation_id="correlation-sdk",
            direction="input",
            stage="input",
        ),
    )
    await detector.shutdown()

    assert isinstance(result.output, DetectionResult)
    assert result.output.modified_content == "sdk redacted"
    assert result.signals == ("safety.modify",)
    assert set(DetectionContext.model_fields) >= {
        "direction",
        "request_id",
        "user_id",
        "metadata",
        "language",
        "message_index",
    }
    assert set(DetectionResult.model_fields) >= {
        "detector_name",
        "category",
        "action",
        "confidence",
        "risk_level",
        "message",
        "details",
        "modified_content",
    }
    assert Modification.model_fields["modified_content"].is_required()


async def test_tc_dca_004() -> None:
    """TC-DCA-004: coordinator reuses lifecycle/status and never creates sentinels."""

    class LifecycleDetector(RecordingDetector):
        def __init__(self, *, fail: bool = False) -> None:
            super().__init__()
            self.fail = fail
            self.initialize_calls = 0
            self.health_calls = 0
            self.shutdown_calls = 0

        async def initialize(self, config: dict[str, Any]) -> None:
            del config
            self.initialize_calls += 1
            if self.fail:
                raise RuntimeError("private initialization failure")

        async def health_check(self) -> bool:
            self.health_calls += 1
            return True

        async def shutdown(self) -> None:
            self.shutdown_calls += 1

    status_registry = DetectorStatusRegistry()
    coordinator = DetectorCapabilityCoordinator(status_registry)
    shared = LifecycleDetector()
    unavailable = LifecycleDetector(fail=True)
    unavailable.name = "unavailable_detector"
    coordinator.register(direction="input", detector=shared, config={})
    coordinator.register(direction="output", detector=shared, config={})
    coordinator.register(direction="input", detector=unavailable, config={})

    await coordinator.initialize_all()
    snapshot = coordinator.snapshot()

    assert shared.initialize_calls == 1
    assert shared.health_calls == 1
    assert snapshot.state("input", shared.name).state is DetectorState.HEALTHY
    assert snapshot.state("output", shared.name).state is DetectorState.HEALTHY
    assert snapshot.adapter("input", shared.name).descriptor.capability_id == (
        "detector.recording_detector"
    )
    assert snapshot.state("input", unavailable.name).state is DetectorState.UNAVAILABLE
    with pytest.raises(KeyError):
        snapshot.adapter("input", unavailable.name)

    await coordinator.shutdown_all()
    assert shared.shutdown_calls == 1


async def test_health_check_error_is_not_reported_as_initialization_error() -> None:
    """TC-DCA-004: evidence distinguishes lifecycle and health-check failures."""

    class HealthErrorDetector(RecordingDetector):
        shutdown_calls = 0

        async def health_check(self) -> bool:
            raise RuntimeError("private health detail")

        async def shutdown(self) -> None:
            self.shutdown_calls += 1

    detector = HealthErrorDetector()
    statuses = DetectorStatusRegistry()
    coordinator = DetectorCapabilityCoordinator(statuses)
    coordinator.register(direction="input", detector=detector, config={})

    await coordinator.initialize_all()
    status = statuses.get("input", detector.name)

    assert status.state is DetectorState.UNHEALTHY
    assert status.reason_code is DetectorReasonCode.HEALTH_CHECK_ERROR
    assert status.loaded is True
    await coordinator.shutdown_all()
    assert detector.shutdown_calls == 1


async def test_tc_dca_005() -> None:
    """TC-DCA-005: adapter propagates errors/cancellation and detector finally cleanup."""

    class FailingDetector(RecordingDetector):
        async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
            del content, context
            raise RuntimeError("endpoint=http://internal token=secret")

    adapter = DetectorCapabilityAdapter(FailingDetector())
    item = FlowItem(item_id="failure-item", content="private content")
    context = FlowContext(
        request_id="failure-request",
        correlation_id="failure-correlation",
        direction="input",
        stage="input",
    )
    with pytest.raises(RuntimeError):
        await adapter.invoke(item, context)

    class CancellingDetector(RecordingDetector):
        def __init__(self) -> None:
            super().__init__()
            self.started = asyncio.Event()
            self.cleaned = asyncio.Event()

        async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
            del content, context
            self.started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cleaned.set()

    cancelling = CancellingDetector()
    cancelling_adapter = DetectorCapabilityAdapter(cancelling)
    invocation = asyncio.create_task(cancelling_adapter.invoke(item, context))
    await asyncio.wait_for(cancelling.started.wait(), timeout=1)
    invocation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await invocation
    assert await asyncio.wait_for(cancelling.cleaned.wait(), timeout=1) is True
