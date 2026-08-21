"""Contract tests for the vendored STDD v2.9.5 CLI."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_upstream_provenance() -> None:
    """TC-STDD-001: provenance pins the official tag, commit, and MIT license."""
    provenance = (PROJECT_ROOT / "STDD_CLI_PROVENANCE.md").read_text(encoding="utf-8")
    assert "https://github.com/leonai42/stdd" in provenance
    assert "v2.9.5" in provenance
    assert "fd9df3104d3588eb145cc84ec551c1803e783c9e" in provenance
    license_text = (PROJECT_ROOT / "stdd" / "UPSTREAM_LICENSE").read_text(encoding="utf-8")
    assert license_text.startswith("MIT License")


def test_vendored_manifest_matches_upstream() -> None:
    """TC-STDD-002: every vendored upstream file matches the pinned manifest."""
    manifest = PROJECT_ROOT / "stdd-v2.9.5.sha256"
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    assert "bin/stdd" in entries
    assert any(path.startswith("stdd/cli/") for path in entries)
    vendored_sources = {"bin/stdd"} | {
        str(path.relative_to(PROJECT_ROOT))
        for path in (PROJECT_ROOT / "stdd").rglob("*")
        if path.is_file()
        and path.name != "UPSTREAM_LICENSE"
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }
    assert set(entries) == vendored_sources
    for relative, expected in entries.items():
        actual = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, relative


def test_help_and_status(tmp_path: Path) -> None:
    """TC-STDD-003: help and status run offline and identify the active change."""
    help_result = subprocess.run(
        [sys.executable, "bin/stdd", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert help_result.returncode == 0, help_result.stderr
    change_id = "cli-status-smoke"
    change_dir = tmp_path / "changes" / change_id
    change_dir.mkdir(parents=True)
    state = {
        "change_id": change_id,
        "status": "in_progress",
        "current_phase": "verify",
        "phases": {
            "understand": {"status": "completed"},
            "spec": {"status": "completed"},
            "verify": {"status": "in_progress"},
        },
    }
    (change_dir / ".stdd.yaml").write_text(
        yaml.safe_dump(state, allow_unicode=True), encoding="utf-8"
    )
    status_result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "bin" / "stdd"), "status", change_id],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert status_result.returncode == 0, status_result.stderr
    assert change_id in status_result.stdout
    assert "当前阶段: verify" in status_result.stdout
    assert "Phase 1: UNDERSTAND (需求理解): completed" in status_result.stdout
    assert "Phase 2: SPEC (规格设计): completed" in status_result.stdout
