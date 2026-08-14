"""Unit tests for zlg detectors CLI (TC-CLI-001~004).

Test cases:
- TC-CLI-001: zlg detectors list (all / --enabled)
- TC-CLI-002: zlg detectors info
- TC-CLI-003: zlg detectors test
- TC-CLI-004: zlg detectors check-connection
"""

from __future__ import annotations

from z_llm_safety_gateway.cli import main as zlg_main


class FakeRegistry:
    """Minimal registry double with built-in + plugin detectors."""

    def __init__(self) -> None:
        self._detectors: dict = {}

    def register(self, name: str, cls) -> None:
        self._detectors[name] = cls

    def list(self) -> list[str]:
        return list(self._detectors.keys())

    def get(self, name: str):
        return self._detectors[name]


class FakeDetector:
    name = "fake"
    category = "custom"
    description = "fake detector"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        pass

    async def detect(self, content: str, context) -> object:
        from z_llm_safety_gateway.models import DetectionResult

        return DetectionResult(
            detector_name=self.name, category=self.category, action="block",
            confidence=0.9, risk_level="high", message="blocked by fake",
        )

    async def health_check(self) -> bool:
        return True


def _run_cli(capsys, monkeypatch, argv: list[str], registry=None) -> int:
    """Run zlg CLI with monkeypatched registry builder."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.cli._build_registry",
        lambda: registry or _default_registry(),
    )
    monkeypatch.setattr("sys.argv", ["zlg", *argv])
    return zlg_main()


def _default_registry():
    reg = FakeRegistry()
    reg.register("prompt_injection", FakeDetector)
    reg.register("fake_plugin", FakeDetector)
    return reg


# --------------------------------------------------------------------------- #
# TC-CLI-001: zlg detectors list
# --------------------------------------------------------------------------- #
def test_detectors_list_all(capsys, monkeypatch) -> None:
    """TC-CLI-001: list shows all detectors (built-in + plugins)."""
    rc = _run_cli(capsys, monkeypatch, ["detectors", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "prompt_injection" in out
    assert "fake_plugin" in out


def test_detectors_list_enabled(capsys, monkeypatch) -> None:
    """TC-CLI-001b: --enabled filters to detectors enabled in config."""
    monkeypatch.setattr(
        "z_llm_safety_gateway.cli.load_config",
        lambda path: _fake_config_enabled_prompt(),
    )
    rc = _run_cli(capsys, monkeypatch, ["detectors", "list", "--enabled"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "prompt_injection" in out  # enabled in config and registered
    assert "fake_plugin" not in out  # registered but not enabled in config


def _fake_config_enabled_prompt():
    """Config enabling prompt_injection (registered) only."""
    from z_llm_safety_gateway.config.models import GatewayConfig
    from z_llm_safety_gateway.config.validators import validate_config

    cfg = GatewayConfig.model_validate(
        {
            "server": {"host": "127.0.0.1", "port": 8080},
            "providers": [
                {"name": "openai", "type": "openai",
                 "base_url": "https://api.openai.com/v1", "api_key": "sk-test"}
            ],
            "routing": {"rules": [{"pattern": "gpt-4*", "provider": "openai"}]},
            "pipeline": {
                "detectors": {
                    "input": [
                        {"name": "prompt_injection", "enabled": True, "config": {}},
                    ],
                    "output": [],
                }
            },
        }
    )
    validate_config(cfg)
    return cfg


# --------------------------------------------------------------------------- #
# TC-CLI-002: zlg detectors info
# --------------------------------------------------------------------------- #
def test_detectors_info_known(capsys, monkeypatch) -> None:
    """TC-CLI-002: info shows detector details."""
    rc = _run_cli(capsys, monkeypatch, ["detectors", "info", "fake_plugin"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fake" in out
    assert "1.0.0" in out


def test_detectors_info_unknown(capsys, monkeypatch) -> None:
    """TC-CLI-002b: unknown detector -> error, non-zero exit."""
    rc = _run_cli(capsys, monkeypatch, ["detectors", "info", "nope"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "nope" in err


# --------------------------------------------------------------------------- #
# TC-CLI-003: zlg detectors test
# --------------------------------------------------------------------------- #
def test_detectors_test_runs_detection(capsys, monkeypatch) -> None:
    """TC-CLI-003: test runs detector and prints result."""
    rc = _run_cli(
        capsys, monkeypatch,
        ["detectors", "test", "fake_plugin", "--input", "bad content"],
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "block" in out
    assert "high" in out


def test_detectors_test_unknown(capsys, monkeypatch) -> None:
    """TC-CLI-003b: test unknown detector -> non-zero exit."""
    rc = _run_cli(capsys, monkeypatch, ["detectors", "test", "nope", "--input", "x"])
    assert rc != 0


# --------------------------------------------------------------------------- #
# TC-CLI-004: zlg detectors check-connection
# --------------------------------------------------------------------------- #
def test_check_connection_ok(capsys, monkeypatch) -> None:
    """TC-CLI-004: check-connection succeeds when sidecar healthy."""

    class FakeGrpc:
        async def initialize(self, config) -> None:
            pass

        async def health_check(self) -> bool:
            return True

        async def shutdown(self) -> None:
            pass

    monkeypatch.setattr(
        "z_llm_safety_gateway.cli._build_grpc_detector",
        lambda cfg: FakeGrpc(),
    )
    monkeypatch.setattr(
        "z_llm_safety_gateway.cli.load_config",
        lambda path: _fake_config(),
    )
    rc = _run_cli(
        capsys, monkeypatch,
        ["detectors", "check-connection", "acme_guard"],
        registry=_default_registry(),
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "serving" in out.lower()


def _fake_config():
    """Build a GatewayConfig containing a type=grpc detector named acme_guard."""
    from z_llm_safety_gateway.config.models import GatewayConfig
    from z_llm_safety_gateway.config.validators import validate_config

    cfg = GatewayConfig.model_validate(
        {
            "server": {"host": "127.0.0.1", "port": 8080},
            "providers": [
                {"name": "openai", "type": "openai",
                 "base_url": "https://api.openai.com/v1", "api_key": "sk-test"}
            ],
            "routing": {"rules": [{"pattern": "gpt-4*", "provider": "openai"}]},
            "pipeline": {
                "detectors": {
                    "input": [
                        {"name": "acme_guard", "type": "grpc", "enabled": True,
                         "config": {"endpoint": "localhost:50051"}}
                    ],
                    "output": [],
                }
            },
        }
    )
    validate_config(cfg)
    return cfg


def test_check_connection_fail(capsys, monkeypatch) -> None:
    """TC-CLI-004b: check-connection failure -> non-zero exit."""

    class FakeGrpc:
        async def initialize(self, config) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def shutdown(self) -> None:
            pass

    monkeypatch.setattr(
        "z_llm_safety_gateway.cli._build_grpc_detector",
        lambda cfg: FakeGrpc(),
    )
    monkeypatch.setattr(
        "z_llm_safety_gateway.cli.load_config",
        lambda path: _fake_config(),
    )
    rc = _run_cli(
        capsys, monkeypatch,
        ["detectors", "check-connection", "acme_guard"],
        registry=_default_registry(),
    )
    assert rc != 0
