"""Unit tests for the plugin loader (TC-PL-001/002/003/004).

Test cases:
- TC-PL-001: entry points discovered and plugins registered
- TC-PL-002: unresolvable entry points skipped with warning, others registered
- TC-PL-003: unknown detector name error includes available list + hint
- TC-PL-004: plugin load failure does not affect built-in detectors
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from z_llm_safety_gateway_sdk import DetectionContext, DetectionResult, Detector

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.config.validators import ConfigValidationError
from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.detectors.registry import DetectorRegistry
from z_llm_safety_gateway.plugins.loader import load_plugins


class PluginDetectorA(Detector):
    name = "plugin_a"
    category = "custom"
    description = "plugin a"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        pass

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name, category=self.category, action="allow",
            confidence=0.0, risk_level="low", message="ok",
        )


def _mk_ep(name: str, module: str, attr: str):
    return SimpleNamespace(name=name, value=f"{module}:{attr}")


def _monkeypatch_entry_points(monkeypatch, eps) -> None:
    def fake(*, group: str | None = None):
        return tuple(eps)

    monkeypatch.setattr("importlib.metadata.entry_points", fake)


def _build_yaml(unknown_name: str = "unknown_detector") -> str:
    import yaml

    cfg = {
        "server": {"host": "127.0.0.1", "port": 8080},
        "providers": [
            {"name": "openai", "type": "openai",
             "base_url": "https://api.openai.com/v1", "api_key": "sk-test"}
        ],
        "routing": {"rules": [{"pattern": "gpt-4*", "provider": "openai"}]},
        "pipeline": {
            "detectors": {
                "input": [{"name": unknown_name, "enabled": True, "config": {}}],
                "output": [],
            }
        },
    }
    return yaml.safe_dump(cfg)


# --------------------------------------------------------------------------- #
# TC-PL-001: entry points discovered and registered
# --------------------------------------------------------------------------- #
def test_load_plugins_registers_entry_points(monkeypatch) -> None:
    """TC-PL-001: load_plugins discovers and registers plugins into registry."""
    _monkeypatch_entry_points(
        monkeypatch,
        [_mk_ep("plugin_a", "tests.unit.plugins.test_loader", "PluginDetectorA")],
    )
    registry = DetectorRegistry()
    count = load_plugins(registry)
    assert count == 1
    assert "plugin_a" in registry.list()
    cls = registry.get("plugin_a")
    assert issubclass(cls, Detector)
    assert cls.name == "plugin_a"


# --------------------------------------------------------------------------- #
# TC-PL-002: bad entry points skipped, others registered
# --------------------------------------------------------------------------- #
def test_load_plugins_skips_bad_entries(monkeypatch, caplog) -> None:
    """TC-PL-002: unresolvable entry points skipped with warning log."""
    _monkeypatch_entry_points(
        monkeypatch,
        [
            _mk_ep("good_plugin", "tests.unit.plugins.test_loader", "PluginDetectorA"),
            _mk_ep("bad_plugin", "no_such_module", "NoClass"),
        ],
    )
    registry = DetectorRegistry()
    count = load_plugins(registry)
    assert count == 1
    assert "good_plugin" in registry.list()
    assert "bad_plugin" not in registry.list()


# --------------------------------------------------------------------------- #
# TC-PL-003: unknown detector name error includes available list + hint
# --------------------------------------------------------------------------- #
def test_unknown_detector_error_includes_available_and_hint(tmp_path, monkeypatch) -> None:
    """TC-PL-003: unknown detector name error lists available detectors + hint."""
    _monkeypatch_entry_points(
        monkeypatch,
        [_mk_ep("plugin_a", "tests.unit.plugins.test_loader", "PluginDetectorA")],
    )
    # Register the plugin into the global registry so validation sees it.
    from z_llm_safety_gateway.plugins import loader as loader_mod

    loader_mod.register_plugins_for_validation(registry=None)

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(_build_yaml("unknown_detector"))

    with pytest.raises(ConfigValidationError) as excinfo:
        load_config(str(cfg_path))
    msg = str(excinfo.value)
    assert "Unknown detector 'unknown_detector'" in msg
    assert "plugin_a" in msg  # discovered plugin listed as available
    assert "use type: grpc" in msg or "type: grpc" in msg  # third-party hint


# --------------------------------------------------------------------------- #
# TC-PL-004: plugin load failure does not affect built-ins
# --------------------------------------------------------------------------- #
def test_load_plugins_keeps_builtins_intact(monkeypatch) -> None:
    """TC-PL-004: load_plugins keeps built-in detectors registered."""
    _monkeypatch_entry_points(
        monkeypatch,
        [_mk_ep("plugin_a", "tests.unit.plugins.test_loader", "PluginDetectorA")],
    )
    registry = create_default_registry()
    before = set(registry.list())
    load_plugins(registry)
    after = set(registry.list())
    assert before <= after  # built-ins preserved
    assert "plugin_a" in after
