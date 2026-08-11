"""Tests for DetectorRegistry: registration, creation, lifecycle management."""

from __future__ import annotations

from typing import Any

import pytest

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.registry import DetectorRegistry
from z_llm_safety_gateway.models import DetectionContext, DetectionResult


class _DummyDetectorA(Detector):
    """First dummy detector for registry tests."""

    name: str = "dummy_a"
    category: str = "test"
    description: str = "dummy detector A"
    version: str = "1.0.0"

    def __init__(self) -> None:
        self.init_config: dict[str, Any] | None = None
        self.shutdown_called = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.init_config = config

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="dummy_a",
        )

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _DummyDetectorB(Detector):
    """Second dummy detector for registry tests."""

    name: str = "dummy_b"
    category: str = "test"
    description: str = "dummy detector B"
    version: str = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        pass

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="flag",
            confidence=0.5,
            risk_level="medium",
            message="dummy_b",
        )


class _FailingInitDetector(Detector):
    """Detector whose initialize raises an exception."""

    name: str = "failing_init"
    category: str = "test"
    description: str = "detector that fails to initialize"
    version: str = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        raise RuntimeError("initialize failed")

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )


class _FailingShutdownDetector(Detector):
    """Detector whose shutdown raises an exception."""

    name: str = "failing_shutdown"
    category: str = "test"
    description: str = "detector that fails on shutdown"
    version: str = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        pass

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )

    async def shutdown(self) -> None:
        raise RuntimeError("shutdown failed")


class TestDetectorRegistryRegistration:
    """REQ-008: DetectorRegistry registration and lookup."""

    def test_register_adds_detector_class(self) -> None:
        """register adds a detector class to the registry."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        assert "dummy_a" in registry.list()

    def test_list_returns_all_registered_names(self) -> None:
        """list returns all registered detector names."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)
        registry.register("dummy_b", _DummyDetectorB)

        names = registry.list()
        assert "dummy_a" in names
        assert "dummy_b" in names
        assert len(names) == 2

    def test_list_returns_empty_for_new_registry(self) -> None:
        """list returns empty list for a new registry."""
        registry = DetectorRegistry()
        assert registry.list() == []

    def test_get_returns_registered_detector_class(self) -> None:
        """get returns the detector class for a registered name."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        detector_class = registry.get("dummy_a")
        assert detector_class is _DummyDetectorA

    def test_get_unregistered_name_raises_keyerror(self) -> None:
        """get raises KeyError for an unregistered name."""
        registry = DetectorRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")


class TestDetectorRegistryCreateDetector:
    """REQ-009: DetectorRegistry.create_detector instantiation and initialization."""

    async def test_create_detector_instantiates_and_initializes(self) -> None:
        """create_detector creates an instance and calls initialize with config."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        config: dict[str, Any] = {"threshold": 0.9}
        detector = await registry.create_detector("dummy_a", config)

        assert isinstance(detector, _DummyDetectorA)
        assert detector.init_config == config

    async def test_create_detector_unregistered_name_raises_keyerror(self) -> None:
        """create_detector raises KeyError for an unregistered name."""
        registry = DetectorRegistry()
        with pytest.raises(KeyError):
            await registry.create_detector("nonexistent", {})

    async def test_create_detector_detect_works_after_creation(self) -> None:
        """Created detector can perform detection."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        detector = await registry.create_detector("dummy_a", {})
        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert result.detector_name == "dummy_a"


class TestDetectorRegistryInitializeAll:
    """REQ-009: DetectorRegistry.initialize_all batch initialization."""

    async def test_initialize_all_creates_all_detectors(self) -> None:
        """initialize_all creates and initializes all configured detectors."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)
        registry.register("dummy_b", _DummyDetectorB)

        detectors_config: dict[str, dict[str, Any]] = {
            "dummy_a": {"threshold": 0.9},
            "dummy_b": {"flag_threshold": 0.5},
        }

        detectors = await registry.initialize_all(detectors_config)

        assert "dummy_a" in detectors
        assert "dummy_b" in detectors
        assert len(detectors) == 2
        assert isinstance(detectors["dummy_a"], _DummyDetectorA)
        assert isinstance(detectors["dummy_b"], _DummyDetectorB)
        assert detectors["dummy_a"].init_config == {"threshold": 0.9}

    async def test_initialize_all_empty_config_returns_empty_dict(self) -> None:
        """initialize_all with empty config returns empty dict."""
        registry = DetectorRegistry()
        detectors = await registry.initialize_all({})
        assert detectors == {}

    async def test_initialize_all_skips_failed_detectors(self) -> None:
        """initialize_all skips detectors that fail to initialize."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)
        registry.register("failing_init", _FailingInitDetector)

        detectors_config: dict[str, dict[str, Any]] = {
            "dummy_a": {},
            "failing_init": {},
        }

        detectors = await registry.initialize_all(detectors_config)

        assert "dummy_a" in detectors
        assert "failing_init" not in detectors
        assert len(detectors) == 1

    async def test_initialize_all_returns_dict_of_detector_instances(self) -> None:
        """initialize_all returns a dict mapping names to Detector instances."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        detectors = await registry.initialize_all({"dummy_a": {}})

        assert isinstance(detectors["dummy_a"], Detector)


class TestDetectorRegistryShutdownAll:
    """REQ-009: DetectorRegistry.shutdown_all batch shutdown."""

    async def test_shutdown_all_calls_shutdown_on_all_detectors(self) -> None:
        """shutdown_all calls shutdown on every detector."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)

        detectors = await registry.initialize_all({"dummy_a": {}})
        await registry.shutdown_all(detectors)

        assert detectors["dummy_a"].shutdown_called is True

    async def test_shutdown_all_empty_dict_does_nothing(self) -> None:
        """shutdown_all with empty dict does not raise."""
        registry = DetectorRegistry()
        await registry.shutdown_all({})

    async def test_shutdown_all_continues_on_failure(self) -> None:
        """shutdown_all does not stop if one detector's shutdown raises."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)
        registry.register("failing_shutdown", _FailingShutdownDetector)

        detectors = await registry.initialize_all(
            {"dummy_a": {}, "failing_shutdown": {}}
        )

        await registry.shutdown_all(detectors)

        assert detectors["dummy_a"].shutdown_called is True

    async def test_shutdown_all_is_static_method(self) -> None:
        """shutdown_all can be called as a static method on the class."""
        registry = DetectorRegistry()
        registry.register("dummy_a", _DummyDetectorA)
        detectors = await registry.initialize_all({"dummy_a": {}})

        await DetectorRegistry.shutdown_all(detectors)

        assert detectors["dummy_a"].shutdown_called is True
