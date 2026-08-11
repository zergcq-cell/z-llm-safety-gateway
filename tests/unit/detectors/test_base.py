"""Tests for the Detector abstract base class."""

from __future__ import annotations

from typing import Any

import pytest

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult


class _StubDetector(Detector):
    """Concrete detector implementation for testing."""

    name: str = "stub_detector"
    category: str = "test"
    description: str = "A stub detector for unit testing"
    version: str = "1.0.0"

    def __init__(self) -> None:
        self.initialized = False
        self.config_received: dict[str, Any] | None = None
        self.shutdown_called = False

    async def initialize(self, config: dict[str, Any]) -> None:
        self.initialized = True
        self.config_received = config

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="stub detection complete",
        )


class _FailingHealthDetector(Detector):
    """Detector that overrides health_check to return False."""

    name: str = "failing_health_detector"
    category: str = "test"
    description: str = "Detector with failing health check"
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

    async def health_check(self) -> bool:
        return False


class _CustomShutdownDetector(Detector):
    """Detector that overrides shutdown with custom logic."""

    name: str = "custom_shutdown_detector"
    category: str = "test"
    description: str = "Detector with custom shutdown"
    version: str = "2.0.0"

    def __init__(self) -> None:
        self.shutdown_called = False

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
        self.shutdown_called = True


class _MissingInitializeDetector(Detector):
    """Detector missing initialize implementation."""

    name: str = "missing_init"
    category: str = "test"
    description: str = "missing init"
    version: str = "0.1.0"

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )


class _MissingDetectDetector(Detector):
    """Detector missing detect implementation."""

    name: str = "missing_detect"
    category: str = "test"
    description: str = "missing detect"
    version: str = "0.1.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        pass


class TestDetectorABC:
    """REQ-001: Detector ABC definition and abstract method enforcement."""

    def test_detector_cannot_be_instantiated_directly(self) -> None:
        """Detector is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            Detector()  # type: ignore[abstract]

    def test_subclass_with_all_methods_can_be_instantiated(self) -> None:
        """A concrete subclass implementing all abstract methods can be instantiated."""
        detector = _StubDetector()
        assert detector is not None

    def test_subclass_missing_initialize_cannot_be_instantiated(self) -> None:
        """A subclass missing initialize cannot be instantiated."""
        with pytest.raises(TypeError):
            _MissingInitializeDetector()  # type: ignore[abstract]

    def test_subclass_missing_detect_cannot_be_instantiated(self) -> None:
        """A subclass missing detect cannot be instantiated."""
        with pytest.raises(TypeError):
            _MissingDetectDetector()  # type: ignore[abstract]

    def test_detector_has_name_attribute(self) -> None:
        """Detector subclass instance has non-empty name."""
        detector = _StubDetector()
        assert detector.name == "stub_detector"
        assert isinstance(detector.name, str)

    def test_detector_has_category_attribute(self) -> None:
        """Detector subclass instance has non-empty category."""
        detector = _StubDetector()
        assert detector.category == "test"
        assert isinstance(detector.category, str)

    def test_detector_has_description_attribute(self) -> None:
        """Detector subclass instance has non-empty description."""
        detector = _StubDetector()
        assert detector.description == "A stub detector for unit testing"
        assert isinstance(detector.description, str)

    def test_detector_has_version_attribute(self) -> None:
        """Detector subclass instance has non-empty version."""
        detector = _StubDetector()
        assert detector.version == "1.0.0"
        assert isinstance(detector.version, str)


class TestDetectorInitialize:
    """REQ-002: Detector.initialize lifecycle method."""

    async def test_initialize_is_async_and_accepts_config(self) -> None:
        """initialize is async and accepts a config dict."""
        detector = _StubDetector()
        config: dict[str, Any] = {"block_threshold": 0.85, "flag_threshold": 0.50}

        await detector.initialize(config)

        assert detector.initialized is True
        assert detector.config_received == config

    async def test_initialize_can_be_called_before_detect(self) -> None:
        """initialize is called before detect."""
        detector = _StubDetector()

        await detector.initialize({"key": "value"})
        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert detector.initialized is True
        assert result.detector_name == detector.name


class TestDetectorDetect:
    """REQ-003: Detector.detect core detection method."""

    async def test_detect_returns_detection_result(self) -> None:
        """detect returns a DetectionResult instance."""
        detector = _StubDetector()
        await detector.initialize({})

        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("Hello world", ctx)

        assert isinstance(result, DetectionResult)

    async def test_detect_result_detector_name_matches(self) -> None:
        """DetectionResult.detector_name matches detector.name."""
        detector = _StubDetector()
        await detector.initialize({})

        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert result.detector_name == detector.name

    async def test_detect_result_category_matches(self) -> None:
        """DetectionResult.category matches detector.category."""
        detector = _StubDetector()
        await detector.initialize({})

        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert result.category == detector.category

    async def test_detect_result_action_is_valid(self) -> None:
        """DetectionResult.action is one of allow/block/flag/modify."""
        detector = _StubDetector()
        await detector.initialize({})

        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert result.action in ("allow", "block", "flag", "modify")

    async def test_detect_result_confidence_in_range(self) -> None:
        """DetectionResult.confidence is between 0.0 and 1.0."""
        detector = _StubDetector()
        await detector.initialize({})

        ctx = DetectionContext(direction="input", request_id="req-1")
        result = await detector.detect("content", ctx)

        assert 0.0 <= result.confidence <= 1.0


class TestDetectorHealthCheck:
    """REQ-004: Detector.health_check method."""

    async def test_health_check_returns_true_by_default(self) -> None:
        """health_check returns True when not overridden."""
        detector = _StubDetector()
        result = await detector.health_check()
        assert result is True

    async def test_health_check_can_be_overridden_to_false(self) -> None:
        """health_check can be overridden to return False."""
        detector = _FailingHealthDetector()
        result = await detector.health_check()
        assert result is False


class TestDetectorShutdown:
    """REQ-005: Detector.shutdown method."""

    async def test_shutdown_default_does_nothing(self) -> None:
        """shutdown by default does nothing and does not raise."""
        detector = _StubDetector()
        await detector.shutdown()
        # No assertion needed — if no exception is raised, the test passes

    async def test_shutdown_can_be_overridden(self) -> None:
        """shutdown can be overridden with custom cleanup logic."""
        detector = _CustomShutdownDetector()
        await detector.shutdown()
        assert detector.shutdown_called is True
