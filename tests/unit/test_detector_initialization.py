"""Unified detector initialization and fatal cleanup tests."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from z_llm_safety_gateway.app import _initialize_detectors
from z_llm_safety_gateway.detectors.status import DetectorState, DetectorStatusRegistry
from z_llm_safety_gateway.exceptions import DetectorInitializationError


class FakeDetector:
    """Small detector lifecycle spy."""

    def __init__(self, name: str, shutdown_order: list[str] | None = None) -> None:
        self.name = name
        self._shutdown_order = shutdown_order

    async def initialize(self, config: dict[str, Any]) -> None:
        return None

    async def shutdown(self) -> None:
        if self._shutdown_order is not None:
            self._shutdown_order.append(self.name)


class HangingShutdownDetector(FakeDetector):
    async def shutdown(self) -> None:
        await asyncio.Event().wait()


class FakeRegistry:
    def __init__(
        self,
        *,
        fail_names: set[str] | None = None,
        shutdown_order: list[str] | None = None,
        none_names: set[str] | None = None,
    ) -> None:
        self.fail_names = fail_names or set()
        self.shutdown_order = shutdown_order
        self.none_names = none_names or set()

    async def create_detector(self, name: str, config: dict[str, Any]) -> FakeDetector:
        if name in self.fail_names:
            raise RuntimeError("endpoint=https://secret token=secret-token")
        if name in self.none_names:
            return None  # type: ignore[return-value]
        return FakeDetector(name, self.shutdown_order)


class AuditSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def flush(self) -> None:
        self.calls.append("flush")

    def close(self) -> None:
        self.calls.append("close")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "config", "expected_type"),
    [
        ("prompt_injection", {}, "builtin"),
        ("toxicity", {}, "ml"),
        ("acme_guard", {}, "in_process"),
        ("grpc_guard", {"type": "grpc"}, "grpc"),
    ],
)
async def test_four_detector_types_share_initialization_coordinator(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    config: dict[str, Any],
    expected_type: str,
) -> None:
    """TC-DF-601: all configured detector types use one status coordinator."""
    if config.get("type") == "grpc":
        monkeypatch.setattr(
            "z_llm_safety_gateway.plugins.grpc.client.GRPCDetector",
            lambda: FakeDetector(name),
        )
    statuses = DetectorStatusRegistry()

    loaded = await _initialize_detectors(
        FakeRegistry(),
        {name: {**config, "on_error": "fail_open", "timeout_seconds": 1.0}},
        direction="input",
        status_registry=statuses,
    )

    record = statuses.get("input", name)
    assert list(loaded) == [name]
    assert record.state is DetectorState.HEALTHY
    assert record.detector_type == expected_type


@pytest.mark.asyncio
async def test_configured_factory_failure_registers_unavailable_without_sentinel() -> None:
    """TC-DF-602: optional factory failure is status, never a fake detector."""
    statuses = DetectorStatusRegistry()

    loaded = await _initialize_detectors(
        FakeRegistry(fail_names={"acme_guard"}),
        {
            "acme_guard": {
                "on_error": "fail_open",
                "required": False,
                "timeout_seconds": 1.0,
            }
        },
        direction="output",
        status_registry=statuses,
    )

    record = statuses.get("output", "acme_guard")
    assert loaded == {}
    assert record.state is DetectorState.UNAVAILABLE
    assert record.detector is None


@pytest.mark.asyncio
async def test_configured_factory_returning_none_is_unavailable() -> None:
    """TC-DF-602: a factory returning no instance is an initialization failure."""
    statuses = DetectorStatusRegistry()
    loaded = await _initialize_detectors(
        FakeRegistry(none_names={"acme_guard"}),
        {"acme_guard": {"on_error": "fail_open", "timeout_seconds": 1.0}},
        direction="input",
        status_registry=statuses,
    )

    assert loaded == {}
    assert statuses.get("input", "acme_guard").state is DetectorState.UNAVAILABLE


@pytest.mark.asyncio
async def test_unavailable_detector_is_not_shut_down() -> None:
    """TC-DF-603: health/shutdown contracts apply only to loaded instances."""
    shutdown_order: list[str] = []
    statuses = DetectorStatusRegistry()
    loaded = await _initialize_detectors(
        FakeRegistry(fail_names={"missing"}, shutdown_order=shutdown_order),
        {
            "loaded": {"on_error": "fail_open", "timeout_seconds": 1.0},
            "missing": {"on_error": "fail_open", "timeout_seconds": 1.0},
        },
        direction="input",
        status_registry=statuses,
    )

    for detector in loaded.values():
        await detector.shutdown()

    assert shutdown_order == ["loaded"]
    assert statuses.get("input", "missing").detector is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "config"),
    [
        ("prompt_injection", {}),
        ("toxicity", {}),
        ("acme_guard", {}),
        ("grpc_guard", {"type": "grpc"}),
    ],
)
async def test_required_initialization_failure_aborts_for_all_types(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    config: dict[str, Any],
) -> None:
    """TC-RDP-001: required failure is fatal for every detector type."""
    registry = FakeRegistry(fail_names={name})
    if config.get("type") == "grpc":
        class FailingGrpc(FakeDetector):
            async def initialize(self, config: dict[str, Any]) -> None:
                raise RuntimeError("secret-token")

        monkeypatch.setattr(
            "z_llm_safety_gateway.plugins.grpc.client.GRPCDetector",
            lambda: FailingGrpc(name),
        )

    with pytest.raises(DetectorInitializationError, match=name):
        await _initialize_detectors(
            registry,
            {
                name: {
                    **config,
                    "required": True,
                    "on_error": "fail_closed",
                    "timeout_seconds": 1.0,
                }
            },
            direction="input",
            status_registry=DetectorStatusRegistry(),
        )


@pytest.mark.asyncio
async def test_required_failure_cleans_loaded_detectors_and_flushes_audit() -> None:
    """TC-RDP-002: fatal startup performs reverse cleanup and audit close."""
    shutdown_order: list[str] = []
    audit = AuditSpy()

    with pytest.raises(DetectorInitializationError):
        await _initialize_detectors(
            FakeRegistry(fail_names={"fatal"}, shutdown_order=shutdown_order),
            {
                "first": {"on_error": "fail_open", "timeout_seconds": 1.0},
                "second": {"on_error": "fail_open", "timeout_seconds": 1.0},
                "fatal": {
                    "required": True,
                    "on_error": "fail_closed",
                    "timeout_seconds": 1.0,
                },
            },
            direction="input",
            status_registry=DetectorStatusRegistry(),
            audit_logger=audit,
        )

    assert shutdown_order == ["second", "first"]
    assert audit.calls == ["flush", "close"]


@pytest.mark.asyncio
async def test_fatal_cleanup_is_bounded_and_still_flushes_audit() -> None:
    """A hanging plugin shutdown cannot suppress fatal startup evidence."""
    class Registry(FakeRegistry):
        async def create_detector(
            self, name: str, config: dict[str, Any]
        ) -> FakeDetector:
            if name == "hanging":
                return HangingShutdownDetector(name)
            return await super().create_detector(name, config)

    audit = AuditSpy()
    with pytest.raises(DetectorInitializationError):
        await asyncio.wait_for(
            _initialize_detectors(
                Registry(fail_names={"fatal"}),
                {
                    "hanging": {"on_error": "fail_open", "timeout_seconds": 0.01},
                    "fatal": {
                        "required": True,
                        "on_error": "fail_closed",
                        "timeout_seconds": 0.01,
                    },
                },
                direction="input",
                status_registry=DetectorStatusRegistry(),
                audit_logger=audit,
            ),
            timeout=0.1,
        )
    assert audit.calls == ["flush", "close"]


@pytest.mark.asyncio
async def test_partially_initialized_grpc_detector_is_cleaned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A constructed gRPC client is closed when initialize raises."""
    cleaned: list[str] = []

    class PartialGrpc(FakeDetector):
        async def initialize(self, config: dict[str, Any]) -> None:
            raise RuntimeError("initialization failed")

        async def shutdown(self) -> None:
            cleaned.append(self.name)

    monkeypatch.setattr(
        "z_llm_safety_gateway.plugins.grpc.client.GRPCDetector",
        lambda: PartialGrpc("grpc_guard"),
    )

    await _initialize_detectors(
        FakeRegistry(),
        {
            "grpc_guard": {
                "type": "grpc",
                "on_error": "fail_open",
                "timeout_seconds": 0.1,
            }
        },
        direction="input",
        status_registry=DetectorStatusRegistry(),
    )

    assert cleaned == ["grpc_guard"]
