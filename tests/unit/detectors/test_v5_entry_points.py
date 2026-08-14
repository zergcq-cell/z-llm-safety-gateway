"""Unit tests for DetectorRegistry entry-points registration (TC-DF-501).

Test cases:
- TC-DF-501: register_from_entry_points discovers and registers plugin classes;
  existing same-name registrations are NOT overwritten; list() includes plugins.
"""

from __future__ import annotations

from types import SimpleNamespace

from z_llm_safety_gateway_sdk import DetectionContext, DetectionResult, Detector

from z_llm_safety_gateway.detectors.registry import DetectorRegistry

#: Module containing FakePluginDetector for entry point simulation.
_MODULE = "tests.unit.detectors.test_v5_entry_points"


class FakePluginDetector(Detector):
    """A plugin detector (importable class for entry point simulation)."""

    name = "fake_plugin"
    category = "custom"
    description = "fake plugin detector"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
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


def _make_entry_point(name: str, module: str, attr: str):
    """Build a mock importlib.metadata.EntryPoint-like object."""
    return SimpleNamespace(
    name=name, value=f"{module}:{attr}", group="z_llm_safety_gateway.detectors"
)


def test_register_from_entry_points_discovers_plugins(monkeypatch) -> None:
    """TC-DF-501: entry points are discovered and registered."""
    ep = _make_entry_point(
        "fake_plugin", _MODULE, "FakePluginDetector"
    )

    def fake_entry_points(*, group: str | None = None):
        assert group == "z_llm_safety_gateway.detectors"
        return (ep,)

    monkeypatch.setattr(
        "importlib.metadata.entry_points", fake_entry_points
    )

    registry = DetectorRegistry()
    registry.register_from_entry_points(group="z_llm_safety_gateway.detectors")

    assert "fake_plugin" in registry.list()
    cls = registry.get("fake_plugin")
    assert cls is FakePluginDetector


def test_register_from_entry_points_does_not_overwrite_existing(monkeypatch) -> None:
    """TC-DF-501b: existing same-name registration wins over entry point."""
    ep = _make_entry_point(
        "fake_plugin", _MODULE, "FakePluginDetector"
    )

    def fake_entry_points(*, group: str | None = None):
        return (ep,)

    monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)

    class BuiltinShadow:
        pass

    registry = DetectorRegistry()
    registry.register("fake_plugin", BuiltinShadow)  # type: ignore[arg-type]
    registry.register_from_entry_points(group="z_llm_safety_gateway.detectors")

    assert registry.get("fake_plugin") is BuiltinShadow


def test_register_from_entry_points_skips_bad_entry_points(monkeypatch) -> None:
    """TC-DF-501c: unresolvable entry points are skipped with a warning, not fatal."""
    good = _make_entry_point(
        "good_plugin", _MODULE, "FakePluginDetector"
    )
    bad = _make_entry_point("bad_plugin", "no_such_module_xyz", "NoClass")

    def fake_entry_points(*, group: str | None = None):
        return (good, bad)

    monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)

    registry = DetectorRegistry()
    registry.register_from_entry_points(group="z_llm_safety_gateway.detectors")

    assert "good_plugin" in registry.list()
    assert "bad_plugin" not in registry.list()


def test_register_from_entry_points_no_entry_points(monkeypatch) -> None:
    """TC-DF-501d: no entry points -> no-op, empty registry."""
    monkeypatch.setattr(
        "importlib.metadata.entry_points", lambda *, group=None: ()
    )
    registry = DetectorRegistry()
    registry.register_from_entry_points(group="z_llm_safety_gateway.detectors")
    assert registry.list() == []


def test_entry_point_loading_with_sdk_detector(monkeypatch) -> None:
    """TC-DF-501e: loaded plugin is a valid SDK Detector subclass."""
    ep = _make_entry_point(
        "fake_plugin", _MODULE, "FakePluginDetector"
    )

    def fake_entry_points(*, group: str | None = None):
        return (ep,)

    monkeypatch.setattr("importlib.metadata.entry_points", fake_entry_points)

    registry = DetectorRegistry()
    registry.register_from_entry_points(group="z_llm_safety_gateway.detectors")
    cls = registry.get("fake_plugin")
    assert issubclass(cls, Detector)
