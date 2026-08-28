"""Executable contracts for the repository-local Codex STDD adapter."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CORE_SKILLS = {
    path.stem for path in (ROOT / ".stdd" / "skills").glob("*.md") if not path.stem.startswith("_")
}
EXPECTED_CODEX_SKILLS = {f"stdd-{name}" for name in CORE_SKILLS}


def _skill_files() -> dict[str, Path]:
    skills_root = ROOT / ".agents" / "skills"
    return {
        path.parent.name: path
        for path in skills_root.glob("stdd-*/SKILL.md")
        if path.is_file()
    }


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n"), "Codex skill must begin with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, "Codex skill frontmatter must have a closing delimiter"
    parsed = yaml.safe_load(text[4:end])
    assert isinstance(parsed, dict)
    return parsed


def _body(text: str) -> str:
    closing = text.find("\n---\n", 4)
    assert closing != -1
    return text[closing + len("\n---\n") :]


def test_codex_project_instructions_are_canonical() -> None:
    """TC-CODEX-001: Codex can discover the mandatory STDD project rules."""
    instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert ".agents/skills/" in instructions
    assert "Understand → Spec → Slice → Build → Verify → Deliver" in instructions
    assert "三道 Gate" in instructions
    assert "PRINCIPLES.md" in instructions
    for principle in (
        "能力插件化，执行 Flow 化，核心保持最小",
        "策略必须显式，失败绝不静默",
        "边界保持透明，契约保持稳定",
        "每一个安全决定都有证据，数据默认受到保护",
    ):
        assert principle in instructions

    project_config = yaml.safe_load(
        (ROOT / ".stdd" / "config.d" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project_config["paths"]["platforms_dir"] == ".agents/skills"


def test_codex_skill_wrappers_match_core_skills() -> None:
    """TC-CODEX-002: the Codex-visible skill set exactly mirrors core STDD skills."""
    assert {
        "understand",
        "spec",
        "slice",
        "build",
        "verify",
        "deliver",
        "upgrade",
    } == CORE_SKILLS
    assert set(_skill_files()) == EXPECTED_CODEX_SKILLS


def test_codex_skill_wrappers_have_valid_frontmatter() -> None:
    """TC-CODEX-003: every thin wrapper has valid metadata and one source of truth."""
    skill_files = _skill_files()
    assert skill_files, "an empty Codex skill collection must never pass"

    for skill_name, skill_file in skill_files.items():
        text = skill_file.read_text(encoding="utf-8")
        metadata = _frontmatter(text)
        core_name = skill_name.removeprefix("stdd-")
        source_reference = f"../../../.stdd/skills/{core_name}.md"

        assert metadata["name"] == skill_name
        assert isinstance(metadata.get("description"), str)
        assert metadata["description"]
        expected_body = (
            f"\n完整读取并严格执行 `{source_reference}`。不得只依据本入口的摘要执行。\n"
        )
        assert _body(text) == expected_body
        assert (skill_file.parent / source_reference).resolve().is_file()


def test_codex_long_range_guidance_is_platform_native() -> None:
    """TC-CODEX-004: long-range authorization uses Codex runtime boundaries."""
    guidance = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / ".stdd" / "skills" / "spec.md",
            ROOT / ".stdd" / "templates" / "long-range-auth.md",
        )
    )
    lowered = guidance.lower()

    assert "codex" in lowered
    assert ".claude" not in lowered
    assert "settings.local.json" not in lowered
    assert "~/.codex" not in lowered
    assert "运行时" in guidance


def test_non_codex_project_adapters_are_absent() -> None:
    """TC-CODEX-005: unsupported project adapters cannot remain active silently."""
    forbidden_paths = (
        ROOT / ".trae" / "skills",
        ROOT / ".stdd" / "platforms" / "claude-code",
        ROOT / ".stdd" / "platforms" / "trae",
        ROOT / ".stdd" / "platforms" / "workbuddy",
    )

    assert all(not path.exists() for path in forbidden_paths)


def test_active_stdd_docs_are_codex_only() -> None:
    """TC-CODEX-007: active overlay docs expose Codex as the sole project adapter."""
    active_docs = [
        ROOT / "AGENTS.md",
        ROOT / "STDD.md",
        *sorted((ROOT / ".stdd" / "skills").rglob("*.md")),
        *sorted((ROOT / ".stdd" / "templates").rglob("*.md")),
        *sorted((ROOT / ".stdd" / "templates").rglob("*.yaml")),
        *sorted((ROOT / ".stdd" / "templates").rglob("*.yml")),
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in active_docs).lower()
    forbidden_markers = (
        ".claude/",
        ".trae/",
        ".workbuddy/",
        ".opencode/",
        ".cursor/",
        "claude code",
        "workbuddy",
        "trae",
        "opencode",
        "cursor",
    )

    assert "codex" in content
    assert all(marker not in content for marker in forbidden_markers)
    assert re.search(
        r"(?<!skills)/stdd-(?:understand|spec|slice|build|verify|deliver|upgrade)",
        content,
    ) is None

    upgrade = (ROOT / ".stdd" / "skills" / "upgrade.md").read_text(encoding="utf-8")
    assert "备份 `.agents/skills/`" in upgrade
    assert "恢复 `.agents/skills/`" in upgrade
    assert "清理暂存目录" in upgrade
