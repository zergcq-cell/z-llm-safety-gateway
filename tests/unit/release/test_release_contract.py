"""Build, distribution, audit, and release workflow contracts."""

from __future__ import annotations

import json
import os
import re
import site
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.metadata import Metadata

from tools import release_checks
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


def _workflow_step(workflow: dict[str, Any], job: str, name: str) -> dict[str, Any]:
    return next(step for step in workflow["jobs"][job]["steps"] if step.get("name") == name)


def _write_release_tree(
    root: Path,
    *,
    gateway_package: str = "0.2.1",
    gateway_runtime: str = "0.2.1",
    sdk_package: str = "0.1.1",
    sdk_runtime: str = "0.1.1",
    changelog: str | None = None,
) -> None:
    """Create the smallest release tree accepted by the version verifier."""
    files = {
        "pyproject.toml": f'version = "{gateway_package}"\n',
        "src/z_llm_safety_gateway/__init__.py": f'__version__ = "{gateway_runtime}"\n',
        "sdk/pyproject.toml": f'version = "{sdk_package}"\n',
        "sdk/src/z_llm_safety_gateway_sdk/__init__.py": f'__version__ = "{sdk_runtime}"\n',
        "CHANGELOG.md": changelog
        if changelog is not None
        else "# Changelog\n\n## [0.2.1] - 2026-08-24\n\nRelease verifier hotfix.\n",
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _create_test_venv(
    path: Path,
    environment: dict[str, str],
    *,
    system_site_packages: bool = False,
) -> Path:
    command = [sys.executable, "-m", "venv"]
    if system_site_packages:
        command.append("--system-site-packages")
    command.extend(["--without-pip", str(path)])
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    python = path / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "ensurepip", "--upgrade", "--default-pip"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return python


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
    """TC-SDK-010: Gateway 0.2.1 and SDK 0.1.1 declarations are internally consistent."""
    gateway_versions = {
        _project_version(ROOT / "pyproject.toml"),
        _module_version(ROOT / "src" / "z_llm_safety_gateway" / "__init__.py"),
    }
    sdk_versions = {
        _project_version(ROOT / "sdk" / "pyproject.toml"),
        _module_version(ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "__init__.py"),
    }
    assert gateway_versions == {"0.2.1"}
    assert sdk_versions == {"0.1.1"}


def test_release_verifier_accepts_independent_gateway_and_sdk_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-008: the Gateway tag does not constrain the independent SDK version."""
    _write_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)

    release_checks.verify_version("v0.2.1")


@pytest.mark.parametrize(
    ("gateway_package", "gateway_runtime"),
    [("0.2.0", "0.2.1"), ("0.2.1", "0.2.0")],
    ids=["package", "runtime"],
)
def test_release_verifier_rejects_gateway_version_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gateway_package: str,
    gateway_runtime: str,
) -> None:
    """TC-REL-009: either Gateway declaration must match the requested tag."""
    _write_release_tree(
        tmp_path,
        gateway_package=gateway_package,
        gateway_runtime=gateway_runtime,
    )
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="gateway version mismatch"):
        release_checks.verify_version("v0.2.1")


def test_release_verifier_rejects_sdk_internal_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-010 / TC-SDK-010: SDK package/runtime mismatch blocks release."""
    _write_release_tree(tmp_path, sdk_runtime="0.1.0")
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="SDK version mismatch"):
        release_checks.verify_version("v0.2.1")


@pytest.mark.parametrize(
    "changelog",
    [
        "# Changelog\n\n## [0.2.0] - 2026-08-23\n\nPrevious release.\n",
        "# Changelog\n\n## [0.2.1] - 2026-08-24\n\n## [0.2.0] - 2026-08-23\n\nPrevious release.\n",
    ],
    ids=["missing", "empty"],
)
def test_release_verifier_requires_exact_non_empty_notes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changelog: str,
) -> None:
    """TC-REL-011: missing or empty target notes cannot pass verification."""
    _write_release_tree(tmp_path, changelog=changelog)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="CHANGELOG has no non-empty 0.2.1 section"):
        release_checks.verify_version("v0.2.1")


def test_ci_dev_dependencies_include_no_isolation_build_backend() -> None:
    """Fresh CI installs must include the backend used by no-isolation builds."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    build_system = pyproject.split("[build-system]", 1)[1].split("[project]", 1)[0]
    dev_dependencies = pyproject.split("dev = [", 1)[1].split("]", 1)[0]

    assert '"hatchling"' in build_system
    assert re.search(r'"hatchling(?:[<>=!~].*)?"', dev_dependencies)


def test_release_notes_extraction_stops_at_adjacent_version() -> None:
    """TC-DOCS-010: extracted 0.2.1 notes cannot include adjacent releases."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "v0.2.1")
    assert "独立版本" in notes
    assert "SDK" in notes and "0.1.1" in notes
    assert "v0.2.0 Release" in notes
    assert "检测器就绪状态" not in notes
    assert "[0.1.1]" not in notes


def test_current_release_notes_document_hotfix_without_rewriting_history() -> None:
    """TC-DOCS-010: notes record the failed v0.2.0 release without claiming success."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "0.2.1")

    assert "v0.2.0 Release" in notes
    assert "失败" in notes
    assert "v0.2.1" in notes
    assert "SDK" in notes and "0.1.1" in notes
    assert "v0.2.0 Release 成功" not in notes


def test_release_payload_accepts_exact_notes_and_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-016: exact GitHub Release JSON passes deterministic validation."""
    _write_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    payload = {
        "tagName": "v0.2.1",
        "body": "Release verifier hotfix.",
        "assets": [
            {"name": "z_llm_safety_gateway-0.2.1-py3-none-any.whl"},
            {"name": "z_llm_safety_gateway-0.2.1.tar.gz"},
            {"name": "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl"},
            {"name": "z_llm_safety_gateway_sdk-0.1.1.tar.gz"},
        ],
    }

    release_checks.verify_release_payload(json.dumps(payload), "v0.2.1")


def test_release_cli_verifies_exact_github_release_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-016: the executable CLI validates the exact GitHub Release payload."""
    payload_path = tmp_path / "release.json"
    payload_path.write_text(
        json.dumps(
            {
                "tagName": "v0.2.1",
                "body": extract_release_notes(
                    (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), "0.2.1"
                ),
                "assets": [
                    {"name": "z_llm_safety_gateway-0.2.1-py3-none-any.whl"},
                    {"name": "z_llm_safety_gateway-0.2.1.tar.gz"},
                    {"name": "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl"},
                    {"name": "z_llm_safety_gateway_sdk-0.1.1.tar.gz"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release_checks.py",
            "github-release",
            "--version",
            "v0.2.1",
            "--input",
            str(payload_path),
        ],
    )

    assert release_checks.main() == 0


@pytest.mark.parametrize("mutation", ["body", "missing_asset", "extra_asset", "tag"])
def test_release_payload_requires_exact_notes_and_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """TC-REL-016: remote Release JSON must match exact notes, tag, and four assets."""
    _write_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    assets = [
        {"name": "z_llm_safety_gateway-0.2.1-py3-none-any.whl"},
        {"name": "z_llm_safety_gateway-0.2.1.tar.gz"},
        {"name": "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl"},
        {"name": "z_llm_safety_gateway_sdk-0.1.1.tar.gz"},
    ]
    payload = {
        "tagName": "v0.2.1",
        "body": "Release verifier hotfix.",
        "assets": assets,
    }
    if mutation == "body":
        payload["body"] = "Release verifier hotfix.\nUnexpected adjacent notes."
    elif mutation == "missing_asset":
        payload["assets"] = assets[:-1]
    elif mutation == "extra_asset":
        payload["assets"] = [*assets, {"name": "unexpected.txt"}]
    else:
        payload["tagName"] = "v0.2.0"

    with pytest.raises(ValueError, match="GitHub Release"):
        release_checks.verify_release_payload(json.dumps(payload), "v0.2.1")


def test_build_produces_four_valid_distribution_artifacts(distributions: Path) -> None:
    """TC-REL-012 / TC-SDK-011: both projects produce exact independent artifacts."""
    artifacts = sorted(distributions.iterdir())
    assert len(artifacts) == 4
    assert sum(path.suffix == ".whl" for path in artifacts) == 2
    assert sum(path.name.endswith(".tar.gz") for path in artifacts) == 2

    metadata: list[tuple[Metadata, str]] = []
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as wheel:
                member = next(
                    name for name in wheel.namelist() if name.endswith(".dist-info/METADATA")
                )
                metadata.append((Metadata.from_email(wheel.read(member), validate=True), "wheel"))
        else:
            with tarfile.open(artifact, "r:gz") as sdist:
                member = next(
                    item for item in sdist.getmembers() if item.name.endswith("/PKG-INFO")
                )
                extracted = sdist.extractfile(member)
                assert extracted is not None
                metadata.append((Metadata.from_email(extracted.read(), validate=True), "sdist"))

    assert {(item.name, str(item.version), kind) for item, kind in metadata} == {
        ("z-llm-safety-gateway", "0.2.1", "wheel"),
        ("z-llm-safety-gateway", "0.2.1", "sdist"),
        ("z-llm-safety-gateway-sdk", "0.1.1", "wheel"),
        ("z-llm-safety-gateway-sdk", "0.1.1", "sdist"),
    }


def test_sdk_independent_install(distributions: Path, tmp_path: Path) -> None:
    """TC-SDK-011: SDK wheel installs and runs without the gateway package."""
    environment = tmp_path / "sdk-venv"
    shim = tmp_path / "python-path"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text("", encoding="utf-8")
    clean_env = os.environ.copy()
    clean_env["PYTHONPATH"] = str(shim)
    python = _create_test_venv(environment, clean_env)
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


def test_combined_wheels_install_and_run_all_cli_entry_points(
    distributions: Path, tmp_path: Path
) -> None:
    """TC-REL-013: wheel overlay exposes all CLIs while reusing installed dependencies."""
    environment = tmp_path / "combined-venv"
    shim = tmp_path / "combined-python-path"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text("", encoding="utf-8")
    clean_env = os.environ.copy()
    clean_env["PYTHONPATH"] = os.pathsep.join([str(shim), *site.getsitepackages()])
    python = _create_test_venv(environment, clean_env, system_site_packages=True)
    gateway_wheel = next(distributions.glob("z_llm_safety_gateway-*.whl"))
    sdk_wheel = next(distributions.glob("z_llm_safety_gateway_sdk-*.whl"))
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            str(gateway_wheel),
            str(sdk_wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    version_check = subprocess.run(
        [
            str(python),
            "-c",
            "import z_llm_safety_gateway as g; "
            "import z_llm_safety_gateway_sdk as s; "
            "assert (g.__version__, s.__version__) == ('0.2.1', '0.1.1')",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    assert version_check.returncode == 0, version_check.stderr

    for entry_point in ("z-safety-gateway", "zlg", "zlg-sdk"):
        result = subprocess.run(
            [str(environment / "bin" / entry_point), "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert result.returncode == 0, f"{entry_point}: {result.stderr}"


def test_release_workflow_has_safe_dry_run_and_tag_only_publish() -> None:
    """TC-REL-014: manual runs verify artifacts but cannot publish a release."""
    workflow = _workflow()
    triggers = workflow.get("on", workflow.get(True))
    assert "dry_run" not in triggers["workflow_dispatch"]["inputs"]
    version_input = triggers["workflow_dispatch"]["inputs"]["version"]
    assert version_input["required"] is True
    assert "default" not in version_input
    assert set(workflow["jobs"]) >= {"quality", "build", "audit", "release"}

    quality_job = workflow["jobs"]["quality"]
    assert quality_job["uses"] == "./.github/workflows/ci.yml"

    release_job = workflow["jobs"]["release"]
    condition = release_job["if"]
    assert "github.event_name == 'push'" in condition
    assert "refs/tags/v" in condition
    assert release_job["needs"] == ["quality", "build", "audit"]

    version_step = _workflow_step(workflow, "build", "Validate version and release notes")
    version_env = version_step["env"]["RELEASE_VERSION"]
    assert (
        version_env
        == "${{ github.event_name == 'push' && github.ref_name || inputs.version }}"
    )

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
