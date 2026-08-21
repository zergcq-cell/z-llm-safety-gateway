"""Build, distribution, audit, and release workflow contracts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.metadata import Metadata

from tools.release_checks import extract_release_notes

ROOT = Path(__file__).resolve().parents[3]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _project_version(pyproject: Path) -> str:
    match = re.search(
        r'^version = "(?P<version>[^"]+)"$',
        pyproject.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None
    return match.group("version")


def _module_version(module_init: Path) -> str:
    match = re.search(
        r'^__version__ = "(?P<version>[^"]+)"$',
        module_init.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None
    return match.group("version")


def _workflow() -> dict[str, Any]:
    loaded = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture(scope="module")
def distributions(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build both projects once without network-dependent isolation."""
    output = tmp_path_factory.mktemp("distributions")
    for project in (ROOT, ROOT / "sdk"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                str(output),
                str(project),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return output


def test_release_versions_and_changelog_are_consistent() -> None:
    """TC-REL-001: both packages and CHANGELOG consistently declare 0.1.1."""
    versions = {
        _project_version(ROOT / "pyproject.toml"),
        _module_version(ROOT / "src" / "z_llm_safety_gateway" / "__init__.py"),
        _project_version(ROOT / "sdk" / "pyproject.toml"),
        _module_version(ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "__init__.py"),
    }
    assert versions == {"0.1.1"}

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = re.search(
        r"^## \[0\.1\.1\].+?(?=^## \[0\.1\.0\])", changelog, re.MULTILINE | re.DOTALL
    )
    assert section is not None
    assert len(section.group(0).strip().splitlines()) >= 5


def test_release_notes_extraction_stops_at_adjacent_version() -> None:
    """TC-REL-006: extracted 0.1.1 notes cannot include adjacent releases."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "v0.1.1")
    assert "检测器就绪状态" in notes
    assert "首个公开测试版" not in notes
    assert "[0.1.0]" not in notes


def test_build_produces_four_valid_distribution_artifacts(distributions: Path) -> None:
    """TC-REL-002: gateway and SDK each produce a valid wheel and sdist."""
    artifacts = sorted(distributions.iterdir())
    assert len(artifacts) == 4
    assert sum(path.suffix == ".whl" for path in artifacts) == 2
    assert sum(path.name.endswith(".tar.gz") for path in artifacts) == 2

    metadata: list[Metadata] = []
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as wheel:
                member = next(
                    name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
                )
                metadata.append(Metadata.from_email(wheel.read(member), validate=True))
        else:
            with tarfile.open(artifact, "r:gz") as sdist:
                member = next(
                    item for item in sdist.getmembers() if item.name.endswith("/PKG-INFO")
                )
                extracted = sdist.extractfile(member)
                assert extracted is not None
                metadata.append(Metadata.from_email(extracted.read(), validate=True))

    assert {(item.name, str(item.version)) for item in metadata} == {
        ("z-llm-safety-gateway", "0.1.1"),
        ("z-llm-safety-gateway-sdk", "0.1.1"),
    }


def test_sdk_independent_install(distributions: Path, tmp_path: Path) -> None:
    """TC-SDK-003: SDK wheel installs and runs without the gateway package."""
    environment = tmp_path / "sdk-venv"
    shim = tmp_path / "python-path"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text("", encoding="utf-8")
    clean_env = os.environ.copy()
    clean_env["PYTHONPATH"] = str(shim)
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(environment)],
        check=True,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    python = environment / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "ensurepip", "--upgrade", "--default-pip"],
        check=True,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    sdk_wheel = next(distributions.glob("z_llm_safety_gateway_sdk-*.whl"))
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(sdk_wheel)],
        check=True,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    result = subprocess.run(
        [str(environment / "bin" / "zlg-sdk"), "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    assert result.returncode == 0, result.stderr
    assert "z LLM Safety Gateway Detector SDK CLI" in result.stdout


def test_release_workflow_has_safe_dry_run_and_tag_only_publish() -> None:
    """TC-REL-005: manual runs verify artifacts but cannot publish a release."""
    workflow = _workflow()
    triggers = workflow.get("on", workflow.get(True))
    assert "dry_run" not in triggers["workflow_dispatch"]["inputs"]
    assert set(workflow["jobs"]) >= {"quality", "build", "audit", "release"}

    quality_job = workflow["jobs"]["quality"]
    assert quality_job["uses"] == "./.github/workflows/ci.yml"

    release_job = workflow["jobs"]["release"]
    condition = release_job["if"]
    assert "github.event_name == 'push'" in condition
    assert "refs/tags/v" in condition
    assert release_job["needs"] == ["quality", "build", "audit"]

    build_commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["build"]["steps"])
    assert "twine check" in build_commands
    for entry_point in ("z-safety-gateway", "zlg", "zlg-sdk"):
        assert f"{entry_point} --help" in build_commands

    audit_commands = "\n".join(
        step.get("run", "") for step in workflow["jobs"]["audit"]["steps"]
    )
    assert "--no-deps --disable-pip" in audit_commands
    assert "setuptools" in audit_commands


def test_dependabot_covers_both_packages_and_actions() -> None:
    """TC-GH-003: dependency updates cover root pip, SDK pip, and Actions."""
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    scopes = {(item["package-ecosystem"], item["directory"]) for item in config["updates"]}
    assert scopes == {("pip", "/"), ("pip", "/sdk"), ("github-actions", "/")}
