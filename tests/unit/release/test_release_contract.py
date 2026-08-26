"""Build, distribution, audit, and release workflow contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import site
import subprocess
import sys
import tarfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.metadata import Metadata

from tools import release_checks
from tools.release_checks import extract_release_notes

ROOT = Path(__file__).resolve().parents[3]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_TOOLS_INPUT = ROOT / "requirements" / "release-tools.in"
RELEASE_TOOLS_LOCK = ROOT / "requirements" / "release-tools.lock"
RELEASE_TOOLS_GUIDE = ROOT / "requirements" / "README.md"

EXPECTED_RELEASE_TOOLS = {
    "build": "1.5.0",
    "hatchling": "1.32.0",
    "pip": "26.2.1",
    "pip-audit": "2.10.1",
    "twine": "7.0.0",
}
EXPECTED_RELEASE_PLATFORM_DEPENDENCIES = {
    # keyring only declares this dependency on Linux. Keeping it as a reviewed direct input
    # makes a lock generated on macOS complete for GitHub's Ubuntu runner as well.
    "secretstorage": "3.5.0",
}


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


def _v022_release_payload(*, draft: bool) -> dict[str, Any]:
    assets = [
        "z_llm_safety_gateway-0.2.2-py3-none-any.whl",
        "z_llm_safety_gateway-0.2.2.tar.gz",
        "z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl",
        "z_llm_safety_gateway_sdk-0.1.1.tar.gz",
    ]
    return {
        "tagName": "v0.2.2",
        "body": "Reproducible release notes.",
        "isDraft": draft,
        "isPrerelease": False,
        "url": "https://github.com/example/gateway/releases/tag/v0.2.2",
        "assets": [
            {
                "name": name,
                "state": "uploaded",
                "size": index + 100,
                "digest": f"sha256:{index + 1:064x}",
            }
            for index, name in enumerate(assets)
        ],
    }


def _v022_expected_digests(payload: dict[str, Any]) -> dict[str, str]:
    return {asset["name"]: asset["digest"] for asset in payload["assets"]}


def _v022_release_tree(root: Path) -> None:
    _write_release_tree(
        root,
        gateway_package="0.2.2",
        gateway_runtime="0.2.2",
        changelog=(
            "# Changelog\n\n## [0.2.2] - 2026-08-25\n\n"
            "Reproducible release notes.\n\n## [0.2.1] - 2026-08-24\n\nPrevious.\n"
        ),
    )


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
    """TC-DOCS-011: Gateway 0.2.2 and SDK 0.1.1 declarations are consistent."""
    gateway_versions = {
        _project_version(ROOT / "pyproject.toml"),
        _module_version(ROOT / "src" / "z_llm_safety_gateway" / "__init__.py"),
    }
    sdk_versions = {
        _project_version(ROOT / "sdk" / "pyproject.toml"),
        _module_version(ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "__init__.py"),
    }
    assert gateway_versions == {"0.2.2"}
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
    """TC-DOCS-013: extracted 0.2.2 notes cannot include adjacent releases."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "v0.2.2")
    assert "Node 24" in notes
    assert "SDK" in notes and "0.1.1" in notes
    assert "v0.2.1 Release" not in notes
    assert "v0.2.0 Release" not in notes
    assert "检测器就绪状态" not in notes


def test_current_release_notes_document_hotfix_without_rewriting_history() -> None:
    """TC-DOCS-010: notes record the failed v0.2.0 release without claiming success."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "0.2.1")

    assert "v0.2.0 Release" in notes
    assert "失败" in notes
    assert "v0.2.1" in notes
    assert "SDK" in notes and "0.1.1" in notes
    assert "v0.2.0 Release 成功" not in notes


def test_current_release_notes_document_reproducibility_without_runtime_changes() -> None:
    """TC-DOCS-013: v0.2.2 notes are scoped and preserve prior release history."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = extract_release_notes(changelog, "0.2.2")

    for required in (
        "Node 24",
        "hash",
        "draft",
        "evidence",
        "Gateway 0.2.2",
        "SDK 0.1.1",
        "运行时",
    ):
        assert required in notes
    for non_goal in ("K8s", "Redis", "新 Provider", "UI", "SBOM", "签名"):
        assert non_goal not in notes

    v021 = extract_release_notes(changelog, "0.2.1")
    v020 = extract_release_notes(changelog, "0.2.0")
    assert "独立版本校验" in v021 and "v0.2.0 Release workflow" in v021
    assert "Flow Foundation" in v020 and "逐节点证据链" in v020


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
        ("z-llm-safety-gateway", "0.2.2", "wheel"),
        ("z-llm-safety-gateway", "0.2.2", "sdist"),
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
            "--force-reinstall",
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
            "assert (g.__version__, s.__version__) == ('0.2.2', '0.1.1')",
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


def test_release_tool_lock_is_hashed_and_complete() -> None:
    """TC-REL-018: release tooling is exact, transitively locked, and hashed."""
    direct_pins: dict[str, str] = {}
    for line in RELEASE_TOOLS_INPUT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, version = stripped.split("==", 1)
        direct_pins[name] = version
    assert direct_pins == EXPECTED_RELEASE_TOOLS | EXPECTED_RELEASE_PLATFORM_DEPENDENCIES

    lock = RELEASE_TOOLS_LOCK.read_text(encoding="utf-8")
    all_requirements = re.findall(
        r"(?m)^(?P<name>[a-zA-Z0-9_.-]+)==(?P<version>[^\s\\]+)", lock
    )
    logical_requirements = re.findall(
        r"(?m)^(?P<name>[a-zA-Z0-9_.-]+)==(?P<version>[^\s\\]+)(?P<body>(?:\s*\\\n\s+--hash=sha256:[0-9a-f]{64})+)",
        lock,
    )
    assert logical_requirements
    assert len(all_requirements) == len({name.lower() for name, _ in all_requirements})
    assert {(name.lower(), version) for name, version in all_requirements} == {
        (name.lower(), version) for name, version, _ in logical_requirements
    }
    locked = {name.lower(): version for name, version, _ in logical_requirements}
    assert all(re.fullmatch(r"[^<>=!~]+", version) for version in locked.values())
    assert {name: locked[name] for name in EXPECTED_RELEASE_TOOLS} == EXPECTED_RELEASE_TOOLS
    assert {
        name: locked[name] for name in EXPECTED_RELEASE_PLATFORM_DEPENDENCIES
    } == EXPECTED_RELEASE_PLATFORM_DEPENDENCIES
    for _, _, hash_block in logical_requirements:
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", hash_block)

    workflow_commands = "\n".join(
        step.get("run", "")
        for job in _workflow()["jobs"].values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
    )
    assert workflow_commands.count(
        "python -m pip install --require-hashes -r requirements/release-tools.lock"
    ) >= 2
    assert not re.search(
        r"pip install[^\n]*(?:\bbuild\b|\btwine\b|\bpip-audit\b)", workflow_commands
    )


def test_dependabot_covers_pinned_release_dependencies() -> None:
    """TC-GH-009: dependency updates preserve lock regeneration and SHA review."""
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    scopes = {(item["package-ecosystem"], item["directory"]) for item in config["updates"]}
    assert scopes == {("pip", "/"), ("pip", "/sdk"), ("github-actions", "/")}

    guide = " ".join(RELEASE_TOOLS_GUIDE.read_text(encoding="utf-8").split())
    for required in (
        "pip-tools==7.6.1",
        "python3.12",
        "pip-compile --generate-hashes --resolver=backtracking",
        "requirements/release-tools.lock",
        "full commit SHA",
        "Node 24",
    ):
        assert required in guide


def test_release_workflow_uses_locked_no_isolation_builds() -> None:
    """TC-REL-019: build and audit share the lock and both packages avoid isolation."""
    workflow = _workflow()
    build_commands = "\n".join(
        step.get("run", "") for step in workflow["jobs"]["build"]["steps"]
    )
    audit_commands = "\n".join(
        step.get("run", "") for step in workflow["jobs"]["audit"]["steps"]
    )
    lock_install = (
        "python -m pip install --require-hashes -r requirements/release-tools.lock"
    )

    assert lock_install in build_commands
    assert lock_install in audit_commands
    assert "python -m build --no-isolation --outdir dist ." in build_commands
    assert "python -m build --no-isolation --outdir dist sdk" in build_commands
    assert "python -m twine check dist/*" in build_commands
    assert not re.search(
        r"pip install[^\n]*(?:\bbuild\b|\btwine\b|\bpip-audit\b)",
        f"{build_commands}\n{audit_commands}",
    )


def test_release_workflow_is_draft_first_and_tag_only() -> None:
    """TC-REL-020: dispatch validates only and tag publication is draft-first."""
    workflow = _workflow()
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"push", "workflow_dispatch"}
    release_job = workflow["jobs"]["release"]
    assert release_job["needs"] == ["quality", "build", "audit"]
    assert "github.event_name == 'push'" in release_job["if"]
    assert "refs/tags/v" in release_job["if"]

    step_names = [step.get("name") for step in release_job["steps"]]
    required_order = [
        "Check Release absence",
        "Generate expected asset digests",
        "Create private draft",
        "Capture remote tag refs",
        "Validate private draft",
        "Publish verified draft",
        "Recheck public Release",
        "Generate release evidence",
        "Upload release evidence",
    ]
    assert [step_names.index(name) for name in required_order] == sorted(
        step_names.index(name) for name in required_order
    )

    commands = "\n".join(step.get("run", "") for step in release_job["steps"])
    assert "release_checks.py absence" in commands
    assert commands.count("gh release create") == 1
    assert "--draft" in commands and "--verify-tag" in commands
    assert "--expected-state draft" in commands
    assert commands.count("--expected-digests expected-digests.json") == 3
    assert "gh release edit" in commands and "--draft=false" in commands
    assert "--expected-state public" in commands
    assert "gh release delete" not in commands
    assert "git push --delete" not in commands

    draft_validation = _workflow_step(workflow, "release", "Validate private draft")["run"]
    assert "gh api --paginate --slurp" in draft_validation
    assert "release_checks.py select-release" in draft_validation
    assert "releases/tags/$GITHUB_REF_NAME" not in draft_validation

    evidence_upload = _workflow_step(workflow, "release", "Upload release evidence")
    assert evidence_upload["with"]["retention-days"] == 90
    assert evidence_upload["with"]["if-no-files-found"] == "error"
    assert "release-evidence" in evidence_upload["with"]["name"]


def test_draft_release_selection_is_unique_and_normalized() -> None:
    """TC-REL-021: draft discovery handles paginated list semantics explicitly."""
    draft = {
        "tag_name": "v0.2.2",
        "body": "Reproducible release notes.",
        "draft": True,
        "prerelease": False,
        "html_url": "https://github.com/example/gateway/releases/tag/untagged-draft",
        "assets": [
            {
                "name": "asset.whl",
                "state": "uploaded",
                "size": 10,
                "digest": f"sha256:{1:064x}",
            }
        ],
    }
    unrelated = {**draft, "tag_name": "v0.2.1"}

    selected = release_checks.select_unique_release(
        json.dumps([[unrelated], [draft]]), "v0.2.2", expected_draft=True
    )

    assert selected == {
        "tagName": "v0.2.2",
        "body": "Reproducible release notes.",
        "isDraft": True,
        "isPrerelease": False,
        "url": "https://github.com/example/gateway/releases/tag/untagged-draft",
        "assets": draft["assets"],
    }

    with pytest.raises(ValueError, match="exactly one"):
        release_checks.select_unique_release(
            json.dumps([[draft, deepcopy(draft)]]), "v0.2.2", expected_draft=True
        )
    with pytest.raises(ValueError, match="exactly one"):
        release_checks.select_unique_release(
            json.dumps([[{**draft, "draft": False}]]), "v0.2.2", expected_draft=True
        )


def test_release_evidence_recovery_is_read_only_and_source_bound() -> None:
    """TC-REL-025: a failed tag run can recover evidence without republishing."""
    workflow = _workflow()
    triggers = workflow.get("on", workflow.get(True))
    dispatch_inputs = triggers["workflow_dispatch"]["inputs"]
    assert dispatch_inputs["recover_evidence"]["type"] == "boolean"
    assert dispatch_inputs["recover_evidence"]["default"] is False
    assert dispatch_inputs["source_run_id"]["type"] == "string"
    assert dispatch_inputs["expected_sha"]["type"] == "string"

    recovery = workflow["jobs"]["evidence-recovery"]
    assert recovery["needs"] == ["quality", "build", "audit"]
    assert "github.event_name == 'workflow_dispatch'" in recovery["if"]
    assert "inputs.recover_evidence" in recovery["if"]
    assert recovery["permissions"] == {"actions": "read", "contents": "read"}

    commands = "\n".join(step.get("run", "") for step in recovery["steps"])
    assert "gh run view \"$SOURCE_RUN_ID\"" in commands
    assert "gh run download \"$SOURCE_RUN_ID\"" in commands
    assert "release_checks.py github-release" in commands
    assert "release_checks.py evidence" in commands
    assert "gh release create" not in commands
    assert "gh release edit" not in commands
    assert "gh release delete" not in commands
    assert "git push" not in commands

    upload = _workflow_step(workflow, "evidence-recovery", "Upload recovered release evidence")
    assert upload["with"]["name"] == "release-evidence-${{ inputs.version }}"
    assert upload["with"]["retention-days"] == 90
    assert upload["with"]["if-no-files-found"] == "error"


def test_release_payload_requires_exact_state_digests_and_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-021: exact draft/public payloads and peeled refs pass."""
    _v022_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    expected_sha = "b" * 40
    refs = {"tag_object": "a" * 40, "peeled_commit": expected_sha}

    draft = _v022_release_payload(draft=True)
    release_checks.verify_release_payload(
        json.dumps(draft),
        "v0.2.2",
        expected_draft=True,
        expected_digests=_v022_expected_digests(draft),
    )
    assert release_checks.verify_release_refs(json.dumps(refs), expected_sha) == (
        "a" * 40,
        expected_sha,
    )

    public = _v022_release_payload(draft=False)
    release_checks.verify_release_payload(
        json.dumps(public),
        "v0.2.2",
        expected_draft=False,
        expected_digests=_v022_expected_digests(public),
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "draft",
        "prerelease",
        "asset_state",
        "missing_digest",
        "bad_digest",
        "wrong_digest",
        "swapped_digests",
        "duplicate_asset",
        "missing_asset",
        "extra_asset",
        "body",
        "tag",
        "blank_tag_object",
        "wrong_peeled_commit",
    ],
)
def test_release_payload_rejects_state_digest_and_ref_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """TC-REL-022: state, digest, asset, notes, tag, and ref mutations fail closed."""
    _v022_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    payload = _v022_release_payload(draft=True)
    expected_digests = _v022_expected_digests(payload)
    refs = {"tag_object": "a" * 40, "peeled_commit": "b" * 40}

    if mutation == "draft":
        payload["isDraft"] = False
    elif mutation == "prerelease":
        payload["isPrerelease"] = True
    elif mutation == "asset_state":
        payload["assets"][0]["state"] = "new"
    elif mutation == "missing_digest":
        payload["assets"][0].pop("digest")
    elif mutation == "bad_digest":
        payload["assets"][0]["digest"] = "sha256:not-a-digest"
    elif mutation == "wrong_digest":
        payload["assets"][0]["digest"] = f"sha256:{9:064x}"
    elif mutation == "swapped_digests":
        first = payload["assets"][0]["digest"]
        payload["assets"][0]["digest"] = payload["assets"][1]["digest"]
        payload["assets"][1]["digest"] = first
    elif mutation == "duplicate_asset":
        payload["assets"][1] = deepcopy(payload["assets"][0])
    elif mutation == "missing_asset":
        payload["assets"].pop()
    elif mutation == "extra_asset":
        payload["assets"].append(
            {
                "name": "release-evidence.json",
                "state": "uploaded",
                "size": 1,
                "digest": f"sha256:{9:064x}",
            }
        )
    elif mutation == "body":
        payload["body"] = "Reproducible release notes.\nUnexpected adjacent notes."
    elif mutation == "tag":
        payload["tagName"] = "v0.2.1"
    elif mutation == "blank_tag_object":
        refs["tag_object"] = ""
    else:
        refs["peeled_commit"] = "c" * 40

    with pytest.raises(ValueError, match="GitHub Release|remote tag refs"):
        if mutation in {"blank_tag_object", "wrong_peeled_commit"}:
            release_checks.verify_release_refs(json.dumps(refs), "b" * 40)
        else:
            release_checks.verify_release_payload(
                json.dumps(payload),
                "v0.2.2",
                expected_draft=True,
                expected_digests=expected_digests,
            )


def test_expected_asset_digests_are_computed_from_local_distributions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-021: expected digests bind each asset name to its local bytes."""
    _v022_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    for index, name in enumerate(release_checks._expected_asset_names("v0.2.2")):
        (dist / name).write_bytes(f"artifact-{index}".encode())

    observed = release_checks.build_expected_asset_digests(dist, "v0.2.2")

    assert observed == {
        path.name: f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in sorted(dist.iterdir())
    }


def test_release_evidence_is_deterministic_bounded_and_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-REL-023 / TC-REL-025: local evidence contract is deterministic and safe."""
    _v022_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    release = _v022_release_payload(draft=False)
    refs = {"tag_object": "a" * 40, "peeled_commit": "b" * 40}
    workflow = {
        "repository": "example/gateway",
        "run_id": 42,
        "run_attempt": 1,
        "run_url": "https://github.com/example/gateway/actions/runs/42",
        "jobs": {
            "quality": "success",
            "build": "success",
            "audit": "success",
            "public_verify": "success",
        },
        "token": "must-not-appear",
        "actor_email": "private@example.com",
    }

    first = release_checks.build_release_evidence(
        json.dumps(release),
        "v0.2.2",
        json.dumps(refs),
        json.dumps(workflow),
        expected_sha="b" * 40,
        expected_digests=_v022_expected_digests(release),
        verified_at="2026-08-25T12:00:00Z",
    )
    release["assets"].reverse()
    workflow["jobs"] = dict(reversed(list(workflow["jobs"].items())))
    second = release_checks.build_release_evidence(
        json.dumps(release),
        "v0.2.2",
        json.dumps(refs),
        json.dumps(workflow),
        expected_sha="b" * 40,
        expected_digests=_v022_expected_digests(release),
        verified_at="2026-08-25T12:00:00Z",
    )

    assert first == second
    assert "must-not-appear" not in first
    assert "private@example.com" not in first
    evidence = json.loads(first)
    assert set(evidence) == {
        "assets",
        "gateway_version",
        "release",
        "sdk_version",
        "tag",
        "tag_object",
        "peeled_commit",
        "verified_at",
        "verifier_schema_version",
        "workflow",
    }
    assert evidence["verifier_schema_version"] == 1
    assert evidence["gateway_version"] == "0.2.2"
    assert evidence["sdk_version"] == "0.1.1"
    assert [asset["name"] for asset in evidence["assets"]] == sorted(
        asset["name"] for asset in evidence["assets"]
    )
    assert len(evidence["assets"]) == 4
    assert evidence["workflow"]["jobs"] == {
        "audit": "success",
        "build": "success",
        "public_verify": "success",
        "quality": "success",
    }
    assert evidence["release"]["is_draft"] is False
    assert re.fullmatch(r"[0-9a-f]{64}", evidence["release"]["notes_sha256"])

    workflow["jobs"]["audit"] = "failure"
    with pytest.raises(ValueError, match="workflow metadata job conclusions"):
        release_checks.build_release_evidence(
            json.dumps(release),
            "v0.2.2",
            json.dumps(refs),
            json.dumps(workflow),
            expected_sha="b" * 40,
            expected_digests=_v022_expected_digests(release),
            verified_at="2026-08-25T12:00:00Z",
        )


@pytest.mark.parametrize(
    ("mutation", "replacement"),
    [
        ("run_url", "https://github.com/other/repo/actions/runs/42"),
        ("release_url", "https://github.com/other/repo/releases/tag/v0.2.2"),
        ("verified_at", "2026-08-25 12:00:00"),
    ],
)
def test_release_evidence_rejects_cross_field_and_timestamp_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    replacement: str,
) -> None:
    """TC-REL-023: schema-v1 URLs and timestamps must agree exactly."""
    _v022_release_tree(tmp_path)
    monkeypatch.setattr(release_checks, "ROOT", tmp_path)
    release = _v022_release_payload(draft=False)
    refs = {"tag_object": "a" * 40, "peeled_commit": "b" * 40}
    workflow = {
        "repository": "example/gateway",
        "run_id": 42,
        "run_attempt": 1,
        "run_url": "https://github.com/example/gateway/actions/runs/42",
        "jobs": {
            "quality": "success",
            "build": "success",
            "audit": "success",
            "public_verify": "success",
        },
    }
    verified_at = "2026-08-25T12:00:00Z"
    if mutation == "run_url":
        workflow["run_url"] = replacement
    elif mutation == "release_url":
        release["url"] = replacement
    else:
        verified_at = replacement

    with pytest.raises(ValueError, match="URL|verified_at"):
        release_checks.build_release_evidence(
            json.dumps(release),
            "v0.2.2",
            json.dumps(refs),
            json.dumps(workflow),
            expected_sha="b" * 40,
            expected_digests=_v022_expected_digests(release),
            verified_at=verified_at,
        )


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_remote_absence_parser_accepts_only_explicit_404(status: int) -> None:
    """TC-REL-024: only a structured HTTP 404 means the Release is absent."""
    assert release_checks.parse_release_absence('{"status": 404}') is True

    with pytest.raises(ValueError, match="Release absence check failed"):
        release_checks.parse_release_absence(json.dumps({"status": status}))
    with pytest.raises(ValueError, match="Release absence check failed"):
        release_checks.parse_release_absence(
            '{"kind": "network_error", "message": "must-not-appear"}'
        )
    with pytest.raises(ValueError, match="Release absence check failed"):
        release_checks.parse_release_absence("not-json")
