"""Tests for deterministic Phase 6 backfill of an archived STDD change."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import yaml

from tools.stdd_backfill import (
    EXPERIENCE_PATTERNS,
    backfill_canonical,
    backfill_experiences,
    backfill_structure,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = PROJECT_ROOT / "bin" / "stdd"
CHANGE = "2026-08-19-detector-readiness-fail-safe"


def _write_archived_change(root: Path) -> Path:
    archive = root / "archive" / CHANGE
    spec_dir = archive / "specs" / "demo"
    spec_dir.mkdir(parents=True)
    proposal = {
        "meta": {"change_id": CHANGE, "title": "Demo", "status": "completed"},
        "why": {"problem": "demo"},
        "what_changes": [],
        "capabilities": {"new": [{"name": "demo", "description": "demo"}]},
        "success_criteria": ["demo"],
    }
    (archive / "proposal.yaml").write_text(yaml.safe_dump(proposal), encoding="utf-8")
    (archive / "proposal.md").write_text("# Demo\n", encoding="utf-8")
    (spec_dir / "agent_spec.yaml").write_text(
        yaml.safe_dump({"meta": {"task_id": "demo"}, "steps": []}), encoding="utf-8"
    )
    return archive


def _tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode())
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def test_canonical_backfill_preserves_archive(tmp_path: Path) -> None:
    """TC-STDD-004: canonical verify succeeds without rewriting the archive."""
    archive = _write_archived_change(tmp_path)
    before = _tree_hash(archive)
    result = backfill_canonical(tmp_path, CHANGE, CLI_PATH, sys.executable)
    assert result.verified is True
    assert _tree_hash(archive) == before
    assert (tmp_path / "canonical" / "proposals" / f"{CHANGE}.yaml").exists()
    assert (tmp_path / "canonical" / "specs" / "agent" / "demo.yaml").exists()


def test_structure_backfill_is_idempotent(tmp_path: Path) -> None:
    """TC-STDD-005: structure backfill records each change and module once."""
    changed_files = ["src/example.py", "tests/unit/test_example.py", "docs/example.md"]
    backfill_structure(tmp_path, CHANGE, changed_files, CLI_PATH, sys.executable)
    backfill_structure(tmp_path, CHANGE, changed_files, CLI_PATH, sys.executable)
    index = yaml.safe_load(
        (tmp_path / ".stdd" / "code-structure" / ".structure-index.yaml").read_text()
    )
    assert index["meta"]["total_changes"] == 1
    assert index["modules"]["src/example.py"]["changes"] == [CHANGE]
    assert index["modules"]["tests/unit/test_example.py"]["changes"] == [CHANGE]


def test_experience_backfill_respects_lifecycle(tmp_path: Path) -> None:
    """TC-STDD-006: discovered experience entries are deduplicated and not promoted."""
    backfill_experiences(tmp_path, CHANGE, CLI_PATH, sys.executable)
    backfill_experiences(tmp_path, CHANGE, CLI_PATH, sys.executable)
    experience_files = sorted((tmp_path / ".stdd" / "experiences").glob("EXP-*.md"))
    assert len(experience_files) == len(EXPERIENCE_PATTERNS) == 3
    for experience_file in experience_files:
        frontmatter = yaml.safe_load(experience_file.read_text().split("---", 2)[1])
        assert frontmatter["lifecycle_state"] == "discovered"
        assert frontmatter["occurrences"] == 1
        assert frontmatter["confidence"] == 0.5
