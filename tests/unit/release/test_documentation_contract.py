"""Version, Quick Start, navigation, and local-link contracts."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

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
    """TC-DOCS-001: public surfaces use v0.1.1 and Python 3.10–3.12."""
    for relative in (
        "README.md",
        "docs/getting-started.md",
        "docs/configuration.md",
        "docs/deployment.md",
        "config/gateway.yaml",
    ):
        assert "v0.1.1" in (ROOT / relative).read_text(encoding="utf-8")

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
    """Plugin guides cannot depend on unpublished packages or advertise mTLS as implemented."""
    files = [
        ROOT / "docs" / "plugin-development.md",
        ROOT / "docs" / "grpc-integration.md",
        ROOT / "docs" / "commercial-plugin.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for path in files:
        assert "适用版本：v0.1.1" in path.read_text(encoding="utf-8")
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
    """Hatch can build examples that depend directly on the GitHub Release SDK wheel."""
    for relative in (
        "examples/plugins/python-inprocess/pyproject.toml",
        "examples/plugins/python-grpc/pyproject.toml",
    ):
        pyproject = (ROOT / relative).read_text(encoding="utf-8")
        assert "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl" in pyproject
        assert "[tool.hatch.metadata]" in pyproject
        assert "allow-direct-references = true" in pyproject
