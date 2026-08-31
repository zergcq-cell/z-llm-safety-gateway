"""Version, Quick Start, navigation, and local-link contracts."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[3]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")


def _active_markdown() -> list[Path]:
    files = list(ROOT.glob("*.md"))
    files += list((ROOT / "docs").glob("*.md"))
    files += list((ROOT / ".github").glob("*.md"))
    files += [ROOT / "sdk" / "README.md"]
    files += list((ROOT / "examples" / "plugins").glob("**/README.md"))
    return sorted(set(files))


def _slug(heading: str) -> str:
    heading = re.sub(r"[^\w\- ]", "", heading.lower(), flags=re.UNICODE)
    return re.sub(r"\s", "-", heading).strip("-")


def _anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if match is None:
            continue
        base = _slug(match.group(1))
        count = counts.get(base, 0)
        anchors.add(base if count == 0 else f"{base}-{count}")
        counts[base] = count + 1
    return anchors


def test_release_version_and_python_support_are_consistent() -> None:
    """TC-DOCS-011: current Gateway surfaces use v0.2.2 and Python 3.10–3.12."""
    expected_surfaces = {
        "README.md": "v0.2.2",
        "docs/getting-started.md": "v0.2.2",
        "docs/configuration.md": "v0.2.2",
        "docs/api-spec.md": "v0.2.2",
        "docs/deployment.md": "v0.2.2",
        "config/gateway.yaml": "v0.2.2",
        "config/gateway.prod.yaml": "v0.2.2",
        "docker-compose.prod.yml": "z-safety-gateway:0.2.2",
    }
    for relative, expected in expected_surfaces.items():
        assert expected in (ROOT / relative).read_text(encoding="utf-8")

    combined = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8")
        for relative in ("README.md", "CONTRIBUTING.md", "docs/getting-started.md")
    )
    assert "3.10–3.12" in combined
    assert "3.12" in combined and "recommended" in combined.lower()
    for relative in ("pyproject.toml", "sdk/pyproject.toml"):
        assert 'requires-python = ">=3.10,<3.13"' in (ROOT / relative).read_text()
    sdk_readme = (ROOT / "sdk" / "README.md").read_text()
    assert "independent version" in sdk_readme.lower()
    assert "class MyDetector(Detector)" in sdk_readme
    assert "async def detect" in sdk_readme

    active_docs = "\n".join(path.read_text(encoding="utf-8") for path in _active_markdown())
    assert "z-llm-safety-gateway-sdk>=1.0,<2.0" not in active_docs
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "| Gateway v0.2.2 | Detector SDK v0.1.1 | Compatible |" in readme


def test_readme_quick_start_matches_executable_source_flow() -> None:
    """TC-DOCS-002: README documents the verified source-install health flow."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quick_start = readme.split("## Quick Start", 1)[1].split("## Documentation", 1)[0]
    for required in (
        "not yet published to PyPI",
        "python3.12 -m venv .venv",
        "pip install -e .",
        "OPENAI_API_KEY",
        "z-safety-gateway --config config/gateway.yaml",
        "curl http://localhost:8080/health",
        "curl http://localhost:8080/ready",
    ):
        assert required in quick_start


def test_active_markdown_has_no_broken_local_links_or_anchors() -> None:
    """TC-DOCS-003: active Markdown navigation contains no local broken links."""
    failures: list[str] = []
    for source in _active_markdown():
        for match in LINK.finditer(source.read_text(encoding="utf-8")):
            target = match.group("target").strip().strip("<>")
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, separator, anchor = target.partition("#")
            destination = (
                source if not file_part else (source.parent / unquote(file_part)).resolve()
            )
            if not destination.is_file():
                failures.append(f"{source.relative_to(ROOT)} -> {target} (missing file)")
                continue
            if separator and destination.suffix.lower() == ".md" and anchor:
                normalized = unquote(anchor).lower()
                if normalized not in _anchors(destination):
                    failures.append(f"{source.relative_to(ROOT)} -> {target} (missing anchor)")
    assert not failures, "\n".join(failures)


def test_configuration_reference_matches_runtime_schema() -> None:
    """Safety-relevant configuration examples use fields the runtime actually consumes."""
    reference = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    routing = reference.split("## routing", 1)[1].split("## pipeline", 1)[0]
    pipeline = reference.split("## pipeline", 1)[1].split("## security", 1)[0]

    assert "ZLG_" not in reference
    assert "openai | azure_openai | openai_compatible" in reference
    assert "flag_escalation" not in routing
    assert "flag_escalation:" in pipeline
    assert "rule:" in pipeline and "action: block" in pipeline
    assert "pipeline:\n  circuit_breaker:" not in reference
    assert "circuit_breaker:" in pipeline
    assert "sync_timeout: 5s" in pipeline


def test_plugin_docs_describe_available_release_and_tls_capabilities() -> None:
    """TC-DOCS-009 / TC-SDK-012: plugin guides preserve independent release roles."""
    files = [
        ROOT / "docs" / "plugin-development.md",
        ROOT / "docs" / "grpc-integration.md",
        ROOT / "docs" / "commercial-plugin.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for path in files:
        contents = path.read_text(encoding="utf-8")
        assert "Gateway v0.2.2" in contents
        assert "SDK v0.1.1" in contents
    assert "SDK v0.2.1" not in combined
    assert "SDK v0.2.2" not in combined
    assert "pip install z-llm-safety-gateway-sdk" not in combined
    assert "pip install z-llm-safety-gateway[grpc]" not in combined
    assert "启用双向信任" not in combined
    assert "tls_enabled: true` + `tls_ca_file`，双向证书" not in combined
    assert "单向 TLS" in combined


def test_conduct_reports_do_not_reuse_the_vulnerability_advisory_channel() -> None:
    """Conduct enforcement has a distinct route from security vulnerability disclosure."""
    conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "/security/advisories/new" not in conduct
    assert "moderation" in conduct.lower()


def test_example_plugins_allow_the_documented_sdk_wheel_reference() -> None:
    """TC-SDK-012: examples keep the available SDK 0.1.1 GitHub wheel reference."""
    for relative in (
        "examples/plugins/python-inprocess/pyproject.toml",
        "examples/plugins/python-grpc/pyproject.toml",
    ):
        pyproject = (ROOT / relative).read_text(encoding="utf-8")
        assert "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl" in pyproject
        assert "z_llm_safety_gateway_sdk-0.2.1" not in pyproject
        assert "z_llm_safety_gateway_sdk-0.2.2" not in pyproject
        assert "[tool.hatch.metadata]" in pyproject
        assert "allow-direct-references = true" in pyproject


def test_sdk_release_surfaces_keep_independent_version() -> None:
    """TC-DOCS-011: SDK surfaces retain the published 0.1.1 release."""
    sdk_readme = (ROOT / "sdk" / "README.md").read_text(encoding="utf-8")
    sdk_cli = (
        ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "cli.py"
    ).read_text(encoding="utf-8")

    assert "Gateway v0.2.2" in sdk_readme
    assert "SDK v0.1.1" in sdk_readme
    assert "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl" in sdk_readme
    assert "v0.1.1/z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl" in sdk_cli
    assert "z_llm_safety_gateway_sdk-0.2.1" not in sdk_readme
    assert "z_llm_safety_gateway_sdk-0.2.1" not in sdk_cli
    assert "z_llm_safety_gateway_sdk-0.2.2" not in sdk_readme
    assert "z_llm_safety_gateway_sdk-0.2.2" not in sdk_cli


def test_design_roadmap_matches_release_history() -> None:
    """TC-DOCS-012: roadmap records v0.2.x facts and leaves v0.3.0 independently scoped."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    versioning = design.split("### Versioning Policy", 1)[1].split(
        "## 18. Development Roadmap", 1
    )[0]
    roadmap = design.split("### Post-v0.1.0 Roadmap", 1)[1].split("\n---\n", 1)[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "current: v0.2.2" in versioning
    for required in (
        "| v0.2.0 | Flow Foundation | Tag published 2026-08-23; Release workflow failed |",
        "| v0.2.1 | Release version hotfix | Released 2026-08-24 |",
        "| v0.2.2 | Release reproducibility and evidence | Released 2026-08-26 |",
        "| v0.3.0 | Multi-tenant safety policy isolation foundation | In progress; change 1/4 "
        "`tenant-identity-config-contract` active |",
    ):
        assert required in roadmap
    for non_goal in ("K8s Helm Chart", "Redis rate limiting", "provider failover", "SBOM"):
        assert non_goal not in roadmap
    assert "Current gateway release version: **v0.2.2**" in readme
    assert "https://github.com/zergcq-cell/z-llm-safety-gateway/releases/tag/v0.2.2" in readme


def _post_v01_roadmap(design: str) -> str:
    return design.split("### Post-v0.1.0 Roadmap", 1)[1].split("\n---\n", 1)[0]


def test_v030_roadmap_has_one_authoritative_source() -> None:
    """TC-RMAP-001: DESIGN owns the sole detailed public version roadmap."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    roadmap = _post_v01_roadmap(design)

    assert "**Authoritative source:** This section is the sole project version roadmap." in roadmap
    for required in ("Version", "Focus", "Status", "Entry criteria", "Completion criteria"):
        assert required in roadmap


def test_v030_version_taxonomy_is_unambiguous() -> None:
    """TC-RMAP-003: internal v0.0.3 and public v0.3.0 have distinct meanings."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    roadmap = _post_v01_roadmap(design)

    assert "Internal `v0.0.3`" in roadmap
    assert "public `v0.3.0`" in roadmap
    assert "Streaming & Audit" in design.split("### Phase 3: v0.0.3", 1)[1]
    assert "| v0.0.3 | Streaming & Audit |" in agents
    assert "| v0.3.0 | Multi-tenant safety policy isolation foundation |" in roadmap


def test_v030_scope_has_one_theme_and_bounded_outcomes() -> None:
    """TC-RMAP-005: public v0.3.0 has one theme and bounded outcome contract."""
    roadmap = _post_v01_roadmap((ROOT / "DESIGN.md").read_text(encoding="utf-8"))

    scope = roadmap.split("#### v0.3.0 Scope Contract", 1)[1]
    for required in (
        "trusted tenant identity",
        "tenant-scoped Flow, policy, detector configuration, and provider routing",
        "tenant-scoped evidence and observability with bounded, non-secret identity",
        "explicit failure and resource isolation",
        "backward-compatible single-tenant operation and transparent provider protocols",
    ):
        assert required in scope
    for excluded_implementation in ("tenant database", "cache technology", "control-plane API"):
        assert excluded_implementation in scope
    assert "not selected by this roadmap" in scope


def test_v030_delivery_is_split_into_independent_stdd_changes() -> None:
    """TC-RMAP-006: four gated changes and aggregate acceptance define delivery."""
    roadmap = _post_v01_roadmap((ROOT / "DESIGN.md").read_text(encoding="utf-8"))

    for change_id in (
        "tenant-identity-config-contract",
        "tenant-flow-policy-resolution",
        "tenant-evidence-observability-isolation",
        "tenant-resource-failure-compatibility",
    ):
        assert change_id in roadmap
    assert (
        "Each implementation change requires explicit Gate 1, Gate 2, and Gate 3 approval."
        in roadmap
    )
    assert "all four changes are delivered" in roadmap
    assert "must not be marked complete or release-ready" in roadmap


def test_v030_active_candidates_are_completely_classified() -> None:
    """TC-RMAP-007: every active v0.3 candidate has one explicit classification."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    roadmap = _post_v01_roadmap(design)

    expected_classifications = {
        "Streaming, sliding-window detection, post-audit, recall, and audit logging": (
            "Completed",
            "Delivered by internal v0.0.3; not public v0.3.0 scope",
        ),
        "Active runtime docstrings/comments under app, audit, config, post_audit, providers, "
        "recall, and streaming, plus legacy config-test annotations": (
            "Completed internal annotations",
            "`v0.3.0` records the original internal implementation label; it is not a public "
            "milestone claim",
        ),
        "Flow Foundation": (
            "Completed",
            "Delivered by public v0.2.0; prerequisite for tenant-scoped composition",
        ),
        "Multi-tenancy configuration and policy isolation": (
            "In public v0.3.0",
            "The sole public v0.3.0 theme, delivered through the four changes above",
        ),
        "Anthropic Claude and Google Gemini providers": (
            "Deferred to independent STDD",
            "No target version is committed",
        ),
        "Multimodal content detection and image generation endpoint": (
            "Deferred to independent STDD",
            "No target version is committed",
        ),
        "OAuth 2.0 integration": (
            "Deferred to independent STDD",
            "No target version is committed",
        ),
        "Bias, malicious URL, and factual-consistency detectors": (
            "Deferred to independent STDD",
            "No target version is committed",
        ),
    }
    classification = roadmap.split("#### v0.3 Candidate Classification", 1)[1]
    table = classification.strip().split("\n\n", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in table.splitlines()[2:]
        if line.startswith("|")
    ]
    assert len(rows) == len(expected_classifications)
    assert {candidate: (category, meaning) for candidate, category, meaning in rows} == (
        expected_classifications
    )

    runtime_root = ROOT / "src" / "z_llm_safety_gateway"
    legacy_modules = {
        path.relative_to(runtime_root).parts[0]
        for path in runtime_root.rglob("*.py")
        if "v0.3.0" in path.read_text(encoding="utf-8")
    }
    assert legacy_modules == {
        "app.py",
        "audit",
        "config",
        "post_audit",
        "providers",
        "recall",
        "streaming",
    }
    for legacy_test in (
        ROOT / "tests" / "unit" / "config" / "test_v3_audit.py",
        ROOT / "tests" / "unit" / "config" / "test_v3_streaming.py",
    ):
        assert "v0.3.0" in legacy_test.read_text(encoding="utf-8")

    assert "| `/v1/images/generations` | Independent STDD change |" in design
    assert "| Anthropic Claude | Independent STDD change |" in design
    assert "| Google Gemini | Independent STDD change |" in design
    assert "| OAuth 2.0 integration | Independent STDD change |" in design


def test_v030_secondary_surfaces_are_bounded_summaries() -> None:
    """TC-RMAP-002: secondary documents summarize and link without a second roadmap."""
    secondary = {
        name: (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "CHANGELOG.md", "AGENTS.md")
    }

    for contents in secondary.values():
        assert "v0.3.0" in contents
        assert "#### v0.3.0 Scope Contract" not in contents
        assert "tenant-identity-config-contract" not in contents
        assert "tenant-resource-failure-compatibility" not in contents
    assert "DESIGN.md#post-v010-roadmap-until-v100-ga" in secondary["README.md"]
    assert "唯一权威来源" in secondary["AGENTS.md"]


def test_v030_roadmap_preserves_release_history() -> None:
    """TC-RMAP-004: v0.2.x tag, workflow, and Release states remain distinct."""
    roadmap = _post_v01_roadmap((ROOT / "DESIGN.md").read_text(encoding="utf-8"))

    for required in (
        "v0.2.0 | Flow Foundation | Tag published 2026-08-23; Release workflow failed",
        "v0.2.1 | Release version hotfix | Released 2026-08-24",
        "v0.2.2 | Release reproducibility and evidence | Released 2026-08-26",
    ):
        assert required in roadmap


def test_v030_historical_references_are_accounted_for_without_rewrite() -> None:
    """TC-RMAP-008: historical v0.3 text remains evidence, not current scope."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    release_notes = (ROOT / "RELEASE_NOTES_v0.1.0.md").read_text(encoding="utf-8")
    archived_proposal = (
        ROOT / "archive" / "2026-08-12-v0.0.3-streaming-audit" / "proposal.md"
    ).read_text(encoding="utf-8")
    merged_project_docs = (ROOT / "specs" / "project-docs" / "spec.md").read_text(
        encoding="utf-8"
    )

    assert "immutable-historical-reference" in _post_v01_roadmap(design)
    assert "v0.3.0 / v0.4.0" in release_notes
    assert "Streaming & Audit" in archived_proposal
    for historical_requirement in ("REQ-DOCS-011", "REQ-DOCS-012", "REQ-DOCS-013"):
        assert historical_requirement in merged_project_docs
    historical_status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--",
            "archive/2026-08-11-v0.0.2-pipeline-detectors",
            "archive/2026-08-12-v0.0.3-streaming-audit",
            "archive/2026-08-12-v0.0.4-security-observability",
            "archive/2026-08-25-v0.2.2-release-reproducibility",
            "archive/2026-08-28-codex-only-stdd-adaptation/potential-requirements.md",
            "canonical/proposals/2026-08-25-v0.2.2-release-reproducibility.yaml",
            "canonical/specs/code/project-docs.yaml",
            "specs/config-system/spec.yaml",
            "RELEASE_NOTES_v0.1.0.md",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert not historical_status.stdout


def test_v030_readme_summary_links_to_authoritative_roadmap() -> None:
    """TC-DOCS-014: README reports active work and links to DESIGN."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    project_status = readme.split("## Project Status", 1)[1].split("## License", 1)[0]

    assert "Next planned milestone: **v0.3.0**" in project_status
    assert "multi-tenant safety policy isolation foundation" in project_status
    assert "first of four implementation changes" in project_status
    assert "tenant-scoped policy isolation is not complete" in project_status
    assert "DESIGN.md#post-v010-roadmap-until-v100-ga" in project_status


def test_v030_changelog_and_project_memory_are_planning_only() -> None:
    """TC-DOCS-015: Secondary summaries report active but incomplete work."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("## [0.2.2]", 1)[0]

    assert "v0.3.0 里程碑范围与 Roadmap" in unreleased
    assert "可信租户身份与配置契约" in unreleased
    assert "租户级策略隔离尚未完成" in unreleased
    assert "| v0.3.0 | Multi-tenant Safety Policy Isolation |" in agents
    assert "进行中：change 1/4 active" in agents
    for false_claim in ("Anthropic/Gemini 已实现", "多模态已实现", "OAuth 已实现"):
        assert false_claim not in unreleased
        assert false_claim not in agents


def test_v030_scope_change_preserves_runtime_and_version_surfaces() -> None:
    """TC-DOCS-016: roadmap tracks active runtime work without premature version claims."""
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    gateway_project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    sdk_project = (ROOT / "sdk" / "pyproject.toml").read_text(encoding="utf-8")
    runtime = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src" / "z_llm_safety_gateway").rglob("*.py"))
    )
    roadmap = _post_v01_roadmap(design)
    assert (
        "**Runtime status:** Implementation in progress through change 1/4\n"
        "(`tenant-identity-config-contract`); no package version change or completed-milestone "
        "claim." in roadmap
    )
    assert 'version = "0.2.2"' in gateway_project
    assert 'version = "0.1.1"' in sdk_project
    assert "tenant_id" in runtime
    assert "All four implementation changes below are delivered" in roadmap


def test_v030_documentation_contract_has_no_false_runtime_claims() -> None:
    """TC-DOCS-017: active documents link correctly and never claim tenant delivery."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    design = ROOT / "DESIGN.md"

    assert "post-v010-roadmap-until-v100-ga" in _anchors(design)
    for false_claim in (
        "multi-tenant runtime is available",
        "multi-tenant support is implemented",
        "多租户运行时已实现",
    ):
        assert false_claim not in readme.lower()
        assert false_claim not in changelog.lower()


def test_v030_agent_checkpoints_reference_collectable_nodes() -> None:
    """Every current roadmap checkpoint must remain bound to a collectable pytest target."""
    change_id = "2026-08-30-v0.3.0-milestone-roadmap"
    locations = [ROOT / "changes" / change_id, ROOT / "archive" / change_id]
    existing_locations = [path for path in locations if path.is_dir()]
    assert len(existing_locations) == 1
    change = existing_locations[0]
    agent_specs = sorted((change / "canonical" / "specs" / "agent").glob("*.yaml"))
    assert [path.stem for path in agent_specs] == ["milestone-scope-governance", "project-docs"]

    targets: list[str] = []
    for agent_spec in agent_specs:
        loaded = yaml.safe_load(agent_spec.read_text(encoding="utf-8"))
        for step in loaded["steps"]:
            targets.extend(
                re.findall(
                    r"tests/[^\s'\"]+(?:::[A-Za-z_][A-Za-z0-9_]*)?",
                    step["action"],
                )
            )

    assert len(targets) == 12
    subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *sorted(set(targets))],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
