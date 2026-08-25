"""Release quality-gate contracts for the GitHub Actions workflow."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
STDD_QUALITY = ROOT / ".stdd" / "config.d" / "quality.yaml"

APPROVED_NODE24_ACTIONS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-python": ("5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0"),
    "actions/upload-artifact": ("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "v7.0.1"),
    "actions/download-artifact": ("3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c", "v8.0.1"),
}


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _release_workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
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


def test_actions_are_node24_approved_sha_pins() -> None:
    """TC-GH-008: every official Action uses its reviewed Node 24 full-SHA pin."""
    action_pattern = re.compile(
        r"uses:\s+(?P<repo>[\w.-]+/[\w.-]+)@(?P<ref>[^\s#]+)\s+#\s+(?P<version>v\d+\.\d+\.\d+)"
    )
    observed: list[tuple[str, str, str]] = []
    for workflow_path in (CI_WORKFLOW, RELEASE_WORKFLOW):
        contents = workflow_path.read_text(encoding="utf-8")
        external_uses = [
            line.strip()
            for line in contents.splitlines()
            if "uses:" in line and "uses: ./" not in line
        ]
        assert external_uses
        matches = list(action_pattern.finditer(contents))
        assert len(matches) == len(external_uses)
        observed.extend(
            (match.group("repo"), match.group("ref"), match.group("version"))
            for match in matches
        )

    assert {repo for repo, _, _ in observed} == set(APPROVED_NODE24_ACTIONS)
    for repo, ref, version in observed:
        assert (ref, version) == APPROVED_NODE24_ACTIONS[repo]
        assert re.fullmatch(r"[0-9a-f]{40}", ref)


def test_release_workflow_uses_least_privilege_and_complete_needs() -> None:
    """TC-GH-010: reusable quality, complete needs, and permissions stay minimal."""
    ci = _workflow()
    release = _release_workflow()
    ci_triggers = ci.get("on", ci.get(True))
    assert "workflow_call" in ci_triggers
    assert ci["permissions"] == {"contents": "read"}
    assert ci["jobs"]["test"]["strategy"]["matrix"]["python-version"] == [
        "3.10",
        "3.11",
        "3.12",
    ]

    assert release["permissions"] == {"contents": "read"}
    assert release["jobs"]["quality"]["uses"] == "./.github/workflows/ci.yml"
    assert release["jobs"]["release"]["needs"] == ["quality", "build", "audit"]
    assert release["jobs"]["release"]["permissions"] == {"contents": "write"}
    for job_name in ("quality", "build", "audit"):
        assert release["jobs"][job_name].get("permissions", {"contents": "read"}) == {
            "contents": "read"
        }
    serialized = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert "actions: write" not in serialized
    assert "id-token: write" not in serialized
