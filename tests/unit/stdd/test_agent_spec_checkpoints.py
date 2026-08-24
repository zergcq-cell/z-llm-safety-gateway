"""Executable checkpoint contracts for the active STDD change."""

from __future__ import annotations

import ast
import re
import shlex
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHANGE_ID = "2026-08-20-v0.1.1-release-hardening"
HOTFIX_CHANGE_ID = "2026-08-23-v0.2.1-release-version-hotfix"
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
