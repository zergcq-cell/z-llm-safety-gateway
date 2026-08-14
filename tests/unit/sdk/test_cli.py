"""Unit tests for zlg-sdk CLI (TC-SDK-003/004/005).

Test cases:
- TC-SDK-003: zlg-sdk new --type python generates runnable project template
- TC-SDK-004: zlg-sdk new --type grpc --language python generates gRPC template
- TC-SDK-005: zlg-sdk validate accepts valid / rejects invalid detector impls
"""

from __future__ import annotations

import sys
from pathlib import Path

from z_llm_safety_gateway_sdk.cli import main as sdk_main
from z_llm_safety_gateway_sdk.cli import validate_detector_module


def _run_sdk(monkeypatch, argv: list[str], cwd: Path) -> int:
    monkeypatch.setattr(sys, "argv", ["zlg-sdk", *argv])
    monkeypatch.chdir(cwd)
    return sdk_main()


# --------------------------------------------------------------------------- #
# TC-SDK-003: zlg-sdk new --type python
# --------------------------------------------------------------------------- #
def test_sdk_new_python_creates_template(tmp_path, monkeypatch) -> None:
    """TC-SDK-003: python template has pyproject.toml with entry points + detector.py."""
    rc = _run_sdk(monkeypatch, ["new", "my-detector", "--type", "python"], tmp_path)
    assert rc == 0

    proj = tmp_path / "my-detector"
    assert (proj / "pyproject.toml").exists()
    assert (proj / "src" / "my_detector" / "detector.py").exists()
    assert (proj / "tests").is_dir()

    pyproject = (proj / "pyproject.toml").read_text()
    assert 'z_llm_safety_gateway.detectors' in pyproject  # entry point group
    assert "z-llm-safety-gateway-sdk" in pyproject  # SDK dependency


def test_sdk_new_python_detector_is_valid(monkeypatch, tmp_path) -> None:
    """TC-SDK-003b: generated detector module validates."""
    _run_sdk(monkeypatch, ["new", "my-detector", "--type", "python"], tmp_path)
    detector_path = tmp_path / "my-detector" / "src" / "my_detector" / "detector.py"
    rc = validate_detector_module(detector_path)
    assert rc == 0


# --------------------------------------------------------------------------- #
# TC-SDK-004: zlg-sdk new --type grpc --language python
# --------------------------------------------------------------------------- #
def test_sdk_new_grpc_creates_server_template(tmp_path, monkeypatch) -> None:
    """TC-SDK-004: grpc template includes a gRPC server module."""
    rc = _run_sdk(
        monkeypatch,
        ["new", "grpc-detector", "--type", "grpc", "--language", "python"],
        tmp_path,
    )
    assert rc == 0
    proj = tmp_path / "grpc-detector"
    assert (proj / "src" / "grpc_detector" / "server.py").exists()
    assert (proj / "src" / "grpc_detector" / "proto").is_dir() or (
        proj / "proto"
    ).is_dir()


# --------------------------------------------------------------------------- #
# TC-SDK-005: zlg-sdk validate
# --------------------------------------------------------------------------- #
VALID_DETECTOR = '''
from z_llm_safety_gateway_sdk import Detector, DetectionContext, DetectionResult


class MyDetector(Detector):
    name = "my_detector"
    category = "custom"
    description = "test"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        pass

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        return DetectionResult(
            detector_name=self.name, category=self.category, action="allow",
            confidence=0.0, risk_level="low", message="ok",
        )
'''

INVALID_DETECTOR = '''
class NotADetector:
    pass
'''


def test_sdk_validate_valid_impl(tmp_path, monkeypatch) -> None:
    """TC-SDK-005: valid Detector subclass passes validation."""
    mod = tmp_path / "my_detector.py"
    mod.write_text(VALID_DETECTOR)
    rc = validate_detector_module(mod)
    assert rc == 0


def test_sdk_validate_invalid_impl(tmp_path, monkeypatch) -> None:
    """TC-SDK-005b: non-Detector class fails validation."""
    mod = tmp_path / "not_a_detector.py"
    mod.write_text(INVALID_DETECTOR)
    rc = validate_detector_module(mod)
    assert rc != 0
