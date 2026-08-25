"""Executable checkpoint contracts for the active STDD change."""

from __future__ import annotations

import ast
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHANGE_ID = "2026-08-20-v0.1.1-release-hardening"
HOTFIX_CHANGE_ID = "2026-08-23-v0.2.1-release-version-hotfix"
REPRO_CHANGE_ID = "2026-08-25-v0.2.2-release-reproducibility"
PYTEST_NODE = re.compile(r"pytest\s+(?P<node>tests/[^\s]+::[A-Za-z_][A-Za-z0-9_]*)")


def _functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    return {node.name for node in ast.walk(tree) if isinstance(node, function_types)}


def _pytest_targets(action: str) -> list[str]:
    return [token for token in shlex.split(action) if token.startswith("tests/")]


def _change_root(change_id: str) -> Path:
    candidates = [ROOT / "changes" / change_id, ROOT / "archive" / change_id]
    change = next((path for path in candidates if path.is_dir()), None)
    assert change is not None, f"missing active or archived change: {change_id}"
    return change


def test_local_pytest_checkpoints_reference_existing_nodes() -> None:
    """Every pytest checkpoint must name a real test file and test function."""
    change = _change_root(CHANGE_ID)
    agent_specs = sorted((change / "specs").glob("*/agent_spec.yaml"))
    assert agent_specs, "change contains no executable agent specs"
    missing: list[str] = []
    for agent_spec in agent_specs:
        loaded: dict[str, Any] = yaml.safe_load(agent_spec.read_text(encoding="utf-8"))
        for step in loaded["steps"]:
            match = PYTEST_NODE.search(step["action"])
            if match is None:
                continue
            file_name, function_name = match.group("node").split("::", maxsplit=1)
            test_file = ROOT / file_name
            if not test_file.is_file() or function_name not in _functions(test_file):
                missing.append(f"{agent_spec.parent.name}/{step['id']}: {match.group('node')}")

    assert missing == []


def test_hotfix_agent_checkpoints_reference_existing_nodes() -> None:
    """All local hotfix checkpoints name archive-stable pytest nodes created by S1–S3."""
    change = _change_root(HOTFIX_CHANGE_ID)
    agent_specs = sorted((change / "canonical" / "specs" / "agent").glob("*.yaml"))
    assert len(agent_specs) == 3

    checked: list[str] = []
    missing: list[str] = []
    for agent_spec in agent_specs:
        loaded: dict[str, Any] = yaml.safe_load(agent_spec.read_text(encoding="utf-8"))
        for step in loaded["steps"]:
            for node in _pytest_targets(step["action"]):
                file_name, _, function_name = node.partition("::")
                test_file = ROOT / file_name
                checked.append(node)
                if not test_file.is_file() or (
                    function_name and function_name not in _functions(test_file)
                ):
                    missing.append(f"{agent_spec.stem}/{step['id']}: {node}")

    assert len(checked) == 23
    assert missing == []


def test_v022_agent_checkpoints_reference_existing_nodes() -> None:
    """TC-GH-011 / TC-REL-025: local nodes and remote handoff remain executable."""
    change = _change_root(REPRO_CHANGE_ID)
    agent_specs = sorted((change / "canonical" / "specs" / "agent").glob("*.yaml"))
    assert len(agent_specs) == 3

    checked: list[str] = []
    missing: list[str] = []
    remote_actions: list[str] = []
    for agent_spec in agent_specs:
        loaded: dict[str, Any] = yaml.safe_load(agent_spec.read_text(encoding="utf-8"))
        for step in loaded["steps"]:
            targets = _pytest_targets(step["action"])
            if not targets:
                remote_actions.append(step["action"])
            for node in targets:
                file_name, _, function_name = node.partition("::")
                test_file = ROOT / file_name
                checked.append(node)
                if not test_file.is_file() or (
                    function_name and function_name not in _functions(test_file)
                ):
                    missing.append(f"{agent_spec.stem}/{step['id']}: {node}")

    assert len(checked) == 19
    assert missing == []
    subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *sorted(set(checked))],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert len(remote_actions) == 3
    for action in remote_actions:
        tokens = shlex.split(action)
        assert tokens[:2] == ["bash", "tools/verify_remote_release.sh"]
        script = ROOT / tokens[1]
        assert script.is_file()
        subprocess.run(["bash", "-n", str(script)], check=True)
    assert {shlex.split(action)[2] for action in remote_actions} == {
        "annotations",
        "pre-tag",
        "release",
    }


def test_v022_docs_checkpoint_covers_all_independent_sdk_surfaces() -> None:
    """CP-DOCS-011 includes SDK docs and example dependency regression nodes."""
    change = _change_root(REPRO_CHANGE_ID)
    spec = yaml.safe_load(
        (change / "canonical" / "specs" / "agent" / "project-docs.yaml").read_text(
            encoding="utf-8"
        )
    )
    action = next(step["action"] for step in spec["steps"] if step["id"] == "CP-DOCS-011")
    assert "test_plugin_docs_describe_available_release_and_tls_capabilities" in action
    assert "test_example_plugins_allow_the_documented_sdk_wheel_reference" in action


def test_remote_annotation_checkpoint_fails_closed_when_jobs_are_unavailable() -> None:
    """The mandatory check-run query cannot hide failure in process substitution."""
    script = (ROOT / "tools" / "verify_remote_release.sh").read_text(encoding="utf-8")
    annotations = script.split('if [[ "$mode" == "annotations" ]]', 1)[1].split(
        "exit 0", 1
    )[0]

    assert "done < <(" not in annotations
    assert 'gh run view "$run_id"' in annotations
    assert 'test -s "$check_ids_file"' in annotations


@pytest.mark.parametrize(
    "runs_payload",
    [
        '[{"databaseId":101,"conclusion":"failure","headSha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]',
        '[{"databaseId":101,"conclusion":"","headSha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]',
        "[]",
    ],
    ids=["failed", "in-progress", "missing"],
)
def test_remote_annotation_checkpoint_rejects_non_successful_runs(
    tmp_path: Path, runs_payload: str
) -> None:
    """Failed, incomplete, or missing mandatory runs cannot produce a green checkpoint."""
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == \"run list\" ]]; then\n"
        f"  printf '%s\\n' '{runs_payload}'\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$1 $2\" == \"run view\" ]]; then\n"
        "  printf '%s\\n' '201'\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$1\" == \"api\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(ROOT / "tools" / "verify_remote_release.sh"),
            "annotations",
            "example/gateway",
            "a" * 40,
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
