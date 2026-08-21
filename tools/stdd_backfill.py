"""Deterministic backfill helpers for an already archived STDD change.

The upstream STDD v2.9.5 CLI expects active changes under ``changes/``.  This
module adapts archived artifacts in a temporary workspace so the upstream CLI
can run without moving or rewriting the archive.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CanonicalBackfillResult:
    """Result of a canonical verification and merge."""

    verified: bool
    stdout: str


EXPERIENCE_PATTERNS: tuple[dict[str, str], ...] = (
    {
        "category": "pipeline_break",
        "pattern": "请求级 detector 过滤必须贯穿同步、流式和 post-audit 路径",
        "root_cause": "重用全局 runner 会在后续阶段重新引入本请求已判定 unavailable 的 detector",
        "detection_trigger": "同一请求的不同检测阶段持有不同 detector 集合",
        "fix_template": "在请求入口构造过滤后的 runner，并向全部后续阶段显式传递",
        "severity": "high",
        "tags": "detector,request-scope,fail-open",
    },
    {
        "category": "content_quality",
        "pattern": "健康检查的外部日志和状态只能暴露稳定 reason code",
        "root_cause": "直接记录 endpoint 或原始异常会泄露内部拓扑和敏感上下文",
        "detection_trigger": "health/readiness 失败日志包含 endpoint、异常文本或动态 label",
        "fix_template": "边界内保留异常用于控制流，边界外映射为稳定且有界的 reason code",
        "severity": "high",
        "tags": "health,logging,sanitization",
    },
    {
        "category": "cascading_errors",
        "pattern": "外层取消也必须在 finally 关闭本地 channel 或部分初始化资源",
        "root_cause": "取消异常会绕过普通 shutdown 尾部逻辑并造成资源泄漏",
        "detection_trigger": "任务取消后本地 channel、client 或部分初始化实例仍保持打开",
        "fix_template": "保持取消语义向上传播，同时在 finally 执行有界的本地资源关闭",
        "severity": "high",
        "tags": "cancellation,cleanup,grpc",
    },
)


def _run_cli(
    cli_path: Path,
    python_executable: str,
    cwd: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [python_executable, str(cli_path), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"STDD CLI failed ({' '.join(arguments)}): {result.stdout}\n{result.stderr}"
        )
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def backfill_canonical(
    project_root: Path,
    change_name: str,
    cli_path: Path,
    python_executable: str,
) -> CanonicalBackfillResult:
    """Verify archived canonical data in a temporary layout and merge it."""
    archive = project_root / "archive" / change_name
    proposal_yaml = archive / "proposal.yaml"
    proposal_md = archive / "proposal.md"
    if not proposal_yaml.exists() or not proposal_md.exists():
        raise FileNotFoundError(f"Archived proposal is incomplete: {archive}")

    with tempfile.TemporaryDirectory(prefix="stdd-canon-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_change = temp_root / "changes" / change_name
        temp_proposals = temp_change / "canonical" / "proposals"
        temp_proposals.mkdir(parents=True)
        shutil.copy2(proposal_yaml, temp_proposals / f"{change_name}.yaml")
        shutil.copy2(proposal_md, temp_change / "proposal.md")
        result = _run_cli(
            cli_path, python_executable, temp_root, "canon", "verify", change_name
        )
        verified = "2/2" in result.stdout or "DC-HASH" in result.stdout

    target_proposal = project_root / "canonical" / "proposals" / f"{change_name}.yaml"
    target_proposal.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(proposal_yaml, target_proposal)

    agent_target = project_root / "canonical" / "specs" / "agent"
    agent_target.mkdir(parents=True, exist_ok=True)
    capabilities: list[str] = []
    for agent_spec in sorted((archive / "specs").glob("*/agent_spec.yaml")):
        capability = agent_spec.parent.name
        capabilities.append(capability)
        shutil.copy2(agent_spec, agent_target / f"{capability}.yaml")

    index_path = project_root / "canonical" / ".canon-index.yaml"
    index = _load_yaml(index_path) if index_path.exists() else {"changes": {}}
    changes = index.setdefault("changes", {})
    changes[change_name] = {
        "proposal": str(target_proposal.relative_to(project_root)),
        "capabilities": capabilities,
        "verified": verified,
    }
    _write_yaml(index_path, index)
    return CanonicalBackfillResult(verified=verified, stdout=result.stdout)


def backfill_structure(
    project_root: Path,
    change_name: str,
    changed_files: list[str],
    cli_path: Path,
    python_executable: str,
) -> None:
    """Run upstream structure merge in temp, then merge an idempotent index."""
    structure_root = project_root / ".stdd" / "code-structure"
    index_path = structure_root / ".structure-index.yaml"
    index: dict[str, Any] = (
        _load_yaml(index_path)
        if index_path.exists()
        else {"meta": {"last_updated": "", "total_changes": 0}, "modules": {}, "changes": []}
    )
    applied = index.setdefault("changes", [])
    if not isinstance(applied, list):
        raise TypeError("structure index 'changes' must be a list")
    if change_name in applied:
        return

    lines = [
        f"# Code Structure Delta — {change_name}",
        "",
        "## 变更文件",
        "",
        *[f"- `{path}`" for path in sorted(set(changed_files))],
        "",
    ]
    delta_content = "\n".join(lines)

    with tempfile.TemporaryDirectory(prefix="stdd-structure-") as temp_dir:
        temp_root = Path(temp_dir)
        delta_path = temp_root / "changes" / change_name / "code-structure-delta.md"
        delta_path.parent.mkdir(parents=True)
        delta_path.write_text(delta_content, encoding="utf-8")
        _run_cli(
            cli_path, python_executable, temp_root, "structure", "merge", change_name
        )

    deltas = structure_root / "deltas"
    deltas.mkdir(parents=True, exist_ok=True)
    (deltas / f"{change_name}.md").write_text(delta_content, encoding="utf-8")

    modules = index.setdefault("modules", {})
    if not isinstance(modules, dict):
        raise TypeError("structure index 'modules' must be a mapping")
    for path in sorted(set(changed_files)):
        module_changes = modules.setdefault(path, {"changes": []})["changes"]
        if change_name not in module_changes:
            module_changes.append(change_name)
    applied.append(change_name)
    meta = index.setdefault("meta", {})
    if not isinstance(meta, dict):
        raise TypeError("structure index 'meta' must be a mapping")
    meta["total_changes"] = len(applied)
    meta["last_updated"] = datetime.now(timezone.utc).isoformat()
    _write_yaml(index_path, index)

    index_md = structure_root / "index.md"
    existing = index_md.read_text(encoding="utf-8") if index_md.exists() else "# 项目代码结构索引\n"
    marker = f"## {change_name}"
    if marker not in existing:
        index_md.write_text(
            existing.rstrip() + f"\n\n{marker}\n\n" + delta_content + "\n",
            encoding="utf-8",
        )


def _experience_frontmatters(experience_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(experience_dir.glob("EXP-*.md")):
        parts = path.read_text(encoding="utf-8").split("---", 2)
        if len(parts) >= 3:
            entries.append(yaml.safe_load(parts[1]) or {})
    return entries


def backfill_experiences(
    project_root: Path,
    change_name: str,
    cli_path: Path,
    python_executable: str,
) -> None:
    """Add missing experience patterns while preserving discovered state."""
    config = project_root / ".stdd" / "config.d" / "experience.yaml"
    if not config.exists():
        _write_yaml(config, {"experience": {"dir": ".stdd/experiences"}})
    experience_dir = project_root / ".stdd" / "experiences"
    existing_patterns = {
        str(entry.get("pattern", "")) for entry in _experience_frontmatters(experience_dir)
    }
    for experience in EXPERIENCE_PATTERNS:
        if experience["pattern"] in existing_patterns:
            continue
        _run_cli(
            cli_path,
            python_executable,
            project_root,
            "experience",
            "add",
            "--category",
            experience["category"],
            "--pattern",
            experience["pattern"],
            "--root-cause",
            experience["root_cause"],
            "--detection-trigger",
            experience["detection_trigger"],
            "--fix-template",
            experience["fix_template"],
            "--language",
            "python",
            "--severity",
            experience["severity"],
            "--tags",
            experience["tags"],
            "--source-change",
            change_name,
            "--project-type",
            "python",
        )


def main() -> int:
    """Backfill the committed detector readiness change in the current project."""
    project_root = Path.cwd()
    cli_path = project_root / "bin" / "stdd"
    change_name = "2026-08-19-detector-readiness-fail-safe"
    backfill_canonical(project_root, change_name, cli_path, sys.executable)
    git_result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "33437bd"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = [line for line in git_result.stdout.splitlines() if line]
    backfill_structure(
        project_root,
        change_name,
        changed_files,
        cli_path,
        sys.executable,
    )
    backfill_experiences(
        project_root,
        change_name,
        cli_path,
        sys.executable,
    )
    print(json.dumps({"change": change_name, "status": "backfilled"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
