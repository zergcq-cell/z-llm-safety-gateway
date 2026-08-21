"""Release quality-gate contracts for the GitHub Actions workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
STDD_QUALITY = ROOT / ".stdd" / "config.d" / "quality.yaml"


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _run_command(step_name: str) -> str:
    steps = _workflow()["jobs"]["test"]["steps"]
    return next(step["run"] for step in steps if step.get("name") == step_name)


def test_ci_covers_all_supported_python_versions() -> None:
    """TC-GH-001: CI exercises every supported Python minor release."""
    triggers = _workflow().get("on", _workflow().get(True))
    assert "workflow_call" in triggers
    versions = _workflow()["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert versions == ["3.10", "3.11", "3.12"]


def test_ci_quality_commands_cover_owned_code() -> None:
    """TC-GH-002: Ruff, Mypy, and coverage include all project-owned code."""
    install = _run_command("Install dependencies")
    assert 'pip install -e ".[dev,grpc]"' in install

    ruff = _run_command("Lint (ruff)")
    assert "tools" in ruff
    assert "examples/plugins/python-inprocess/tests" in ruff
    assert "examples/plugins/python-grpc/tests" in ruff

    mypy = _run_command("Type check (mypy)")
    assert "src/" in mypy
    assert "sdk/src" in mypy
    assert "tools" in mypy

    pytest = _run_command("Test (pytest with coverage gate)")
    assert "--cov-fail-under=90" in pytest
    assert "examples/plugins/python-inprocess/tests" in pytest
    assert "examples/plugins/python-grpc/tests" in pytest


def test_stdd_quality_commands_match_release_gate() -> None:
    """TC-GH-002: STDD Verify cannot silently use weaker local gates than CI."""
    quality = yaml.safe_load(STDD_QUALITY.read_text(encoding="utf-8"))
    assert quality["test"]["coverage_target"] == 90
    assert "--cov-fail-under=0" in quality["quality"]["test"]
    assert "--cov-fail-under=90" in quality["quality"]["release_test"]
    assert "tools/" in quality["quality"]["lint"]
    assert "sdk/src" in quality["quality"]["typecheck"]


def test_dev_dependencies_include_release_test_tooling() -> None:
    """TC-GH-002: a dev install includes tooling imported by the release tests."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"build>=1.2.1"' in pyproject
