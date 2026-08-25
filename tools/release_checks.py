#!/usr/bin/env python3
"""Deterministic local checks shared by release CI and tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA256_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
GIT_SHA = re.compile(r"[0-9a-f]{40}")
REQUIRED_EVIDENCE_JOBS = {"quality", "build", "audit", "public_verify"}
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def _declared_version(path: Path, key: str) -> str:
    match = re.search(
        rf'^{re.escape(key)} = "(?P<version>[^"]+)"$',
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"missing {key} in {path}")
    return match.group("version")


def extract_release_notes(changelog: str, version: str) -> str:
    """Return exactly one non-empty Keep a Changelog version section body."""
    normalized = version.removeprefix("v")
    pattern = re.compile(
        rf"^## \[{re.escape(normalized)}\][^\n]*\n(?P<body>.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog)
    if match is None or not match.group("body").strip():
        raise ValueError(f"CHANGELOG has no non-empty {normalized} section")
    return match.group("body").strip()


def verify_version(version: str) -> None:
    """Verify gateway/SDK metadata, runtime versions, and release notes."""
    normalized = version.removeprefix("v")
    gateway_versions = {
        _declared_version(ROOT / "pyproject.toml", "version"),
        _declared_version(ROOT / "src" / "z_llm_safety_gateway" / "__init__.py", "__version__"),
    }
    if gateway_versions != {normalized}:
        raise ValueError(
            f"gateway version mismatch: expected {normalized}, "
            f"found {sorted(gateway_versions)}"
        )

    sdk_versions = {
        _declared_version(ROOT / "sdk" / "pyproject.toml", "version"),
        _declared_version(
            ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "__init__.py",
            "__version__",
        ),
    }
    if len(sdk_versions) != 1:
        raise ValueError(f"SDK version mismatch: found {sorted(sdk_versions)}")

    extract_release_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), normalized)


def _load_json_object(payload: str, description: str) -> dict[str, Any]:
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"{description} must be valid JSON") from error
    if not isinstance(loaded, dict):
        raise ValueError(f"{description} must be an object")
    return loaded


def _expected_asset_names(version: str) -> list[str]:
    normalized = version.removeprefix("v")
    sdk_version = _declared_version(ROOT / "sdk" / "pyproject.toml", "version")
    return sorted(
        [
            f"z_llm_safety_gateway-{normalized}-py3-none-any.whl",
            f"z_llm_safety_gateway-{normalized}.tar.gz",
            f"z_llm_safety_gateway_sdk-{sdk_version}-py3-none-any.whl",
            f"z_llm_safety_gateway_sdk-{sdk_version}.tar.gz",
        ]
    )


def build_expected_asset_digests(dist_dir: Path, version: str) -> dict[str, str]:
    """Hash exactly the four local distributions expected for a Gateway release."""
    expected_names = _expected_asset_names(version)
    artifacts = sorted(path for path in dist_dir.iterdir() if path.is_file())
    actual_names = [path.name for path in artifacts]
    if actual_names != expected_names:
        raise ValueError(
            f"local distribution assets mismatch: expected {expected_names}, "
            f"found {actual_names}"
        )
    return {
        path.name: f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in artifacts
    }


def _validated_expected_digests(
    expected_digests: dict[str, str], version: str
) -> dict[str, str]:
    expected_names = _expected_asset_names(version)
    if sorted(expected_digests) != expected_names:
        raise ValueError("expected asset digests do not match the four release assets")
    if any(
        not isinstance(digest, str) or SHA256_DIGEST.fullmatch(digest) is None
        for digest in expected_digests.values()
    ):
        raise ValueError("expected asset digest must be sha256")
    return expected_digests


def verify_release_payload(
    payload: str,
    version: str,
    *,
    expected_draft: bool | None = None,
    expected_digests: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Verify exact GitHub Release notes, assets, and optionally publication state."""
    loaded = _load_json_object(payload, "GitHub Release payload")

    normalized = version.removeprefix("v")
    expected_tag = f"v{normalized}"
    if loaded.get("tagName") != expected_tag:
        raise ValueError(
            f"GitHub Release tag mismatch: expected {expected_tag}, found {loaded.get('tagName')}"
        )

    expected_notes = extract_release_notes(
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), normalized
    )
    body = loaded.get("body")
    if not isinstance(body, str) or body.rstrip("\n") != expected_notes.rstrip("\n"):
        raise ValueError("GitHub Release notes do not exactly match CHANGELOG")

    if expected_draft is not None:
        if loaded.get("isDraft") is not expected_draft:
            raise ValueError(
                f"GitHub Release draft state mismatch: expected {expected_draft}"
            )
        if loaded.get("isPrerelease") is not False:
            raise ValueError("GitHub Release prerelease state must be false")

    expected_assets = _expected_asset_names(version)
    if expected_draft is not None and expected_digests is None:
        raise ValueError("expected asset digests are required for stateful validation")
    validated_digests = (
        _validated_expected_digests(expected_digests, version)
        if expected_digests is not None
        else None
    )
    asset_entries = loaded.get("assets")
    if not isinstance(asset_entries, list):
        raise ValueError("GitHub Release assets must be a list")
    actual_assets: list[str] = []
    for entry in asset_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError("GitHub Release asset is missing a name")
        if expected_draft is not None:
            if entry.get("state") != "uploaded":
                raise ValueError("GitHub Release asset state must be uploaded")
            digest = entry.get("digest")
            if not isinstance(digest, str) or SHA256_DIGEST.fullmatch(digest) is None:
                raise ValueError("GitHub Release asset digest must be sha256")
            if validated_digests is not None and digest != validated_digests.get(entry["name"]):
                raise ValueError(
                    f"GitHub Release asset digest mismatch for {entry['name']}"
                )
            size = entry.get("size")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError("GitHub Release asset size must be a non-negative integer")
        actual_assets.append(entry["name"])
    if sorted(actual_assets) != expected_assets:
        raise ValueError(
            f"GitHub Release assets mismatch: expected {expected_assets}, "
            f"found {sorted(actual_assets)}"
        )
    return loaded


def verify_release_refs(refs_payload: str, expected_sha: str) -> tuple[str, str]:
    """Verify the tag object and peeled commit captured from the GitHub refs API."""
    refs = _load_json_object(refs_payload, "remote tag refs")
    tag_object = refs.get("tag_object")
    peeled_commit = refs.get("peeled_commit")
    if not isinstance(tag_object, str) or GIT_SHA.fullmatch(tag_object) is None:
        raise ValueError("remote tag refs contain an invalid tag object")
    if not isinstance(peeled_commit, str) or GIT_SHA.fullmatch(peeled_commit) is None:
        raise ValueError("remote tag refs contain an invalid peeled commit")
    if GIT_SHA.fullmatch(expected_sha) is None or peeled_commit != expected_sha:
        raise ValueError("remote tag refs peeled commit does not match the verified SHA")
    return tag_object, peeled_commit


def parse_release_absence(payload: str) -> bool:
    """Accept only a structured HTTP 404 as evidence that a Release is absent."""
    try:
        evidence = _load_json_object(payload, "Release absence evidence")
    except ValueError as error:
        raise ValueError("Release absence check failed: invalid_json") from error
    status = evidence.get("status")
    if status == 404:
        return True
    reason = f"http_{status}" if isinstance(status, int) else "non_http_failure"
    raise ValueError(f"Release absence check failed: {reason}")


def _validated_workflow_metadata(payload: str) -> dict[str, Any]:
    workflow = _load_json_object(payload, "workflow metadata")
    repository = workflow.get("repository")
    run_id = workflow.get("run_id")
    run_attempt = workflow.get("run_attempt")
    run_url = workflow.get("run_url")
    jobs = workflow.get("jobs")
    if not isinstance(repository, str) or re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ) is None:
        raise ValueError("workflow metadata repository is invalid")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError("workflow metadata run_id is invalid")
    if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1:
        raise ValueError("workflow metadata run_attempt is invalid")
    expected_run_url = f"https://github.com/{repository}/actions/runs/{run_id}"
    if run_url != expected_run_url:
        raise ValueError("workflow metadata run URL is invalid")
    if not isinstance(jobs, dict) or set(jobs) != REQUIRED_EVIDENCE_JOBS:
        raise ValueError("workflow metadata jobs are invalid")
    if not all(isinstance(name, str) and isinstance(result, str) for name, result in jobs.items()):
        raise ValueError("workflow metadata job conclusions are invalid")
    if any(result != "success" for result in jobs.values()):
        raise ValueError("workflow metadata job conclusions must all be success")
    return {
        "jobs": dict(sorted(jobs.items())),
        "repository": repository,
        "run_attempt": run_attempt,
        "run_id": run_id,
        "run_url": run_url,
    }


def build_release_evidence(
    release_payload: str,
    version: str,
    refs_payload: str,
    workflow_payload: str,
    *,
    expected_sha: str,
    expected_digests: dict[str, str],
    verified_at: str,
) -> str:
    """Build deterministic schema-v1 evidence from already-public release metadata."""
    release = verify_release_payload(
        release_payload,
        version,
        expected_draft=False,
        expected_digests=expected_digests,
    )
    workflow = _validated_workflow_metadata(workflow_payload)
    tag_object, peeled_commit = verify_release_refs(refs_payload, expected_sha)
    release_url = release.get("url")
    normalized = version.removeprefix("v")
    expected_release_url = (
        f"https://github.com/{workflow['repository']}/releases/tag/v{normalized}"
    )
    if release_url != expected_release_url:
        raise ValueError("GitHub Release URL is invalid")
    if UTC_TIMESTAMP.fullmatch(verified_at) is None:
        raise ValueError("verified_at must be an RFC3339 UTC timestamp")
    try:
        datetime.strptime(verified_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError("verified_at must be an RFC3339 UTC timestamp") from error

    assets = sorted(
        (
            {
                "digest": entry["digest"],
                "name": entry["name"],
                "size": entry["size"],
            }
            for entry in release["assets"]
        ),
        key=lambda entry: entry["name"],
    )
    sdk_version = _declared_version(ROOT / "sdk" / "pyproject.toml", "version")
    notes = extract_release_notes(
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), normalized
    )
    evidence = {
        "assets": assets,
        "gateway_version": normalized,
        "peeled_commit": peeled_commit,
        "release": {
            "is_draft": release["isDraft"],
            "is_prerelease": release["isPrerelease"],
            "notes_sha256": hashlib.sha256(notes.encode("utf-8")).hexdigest(),
            "url": release_url,
        },
        "sdk_version": sdk_version,
        "tag": f"v{normalized}",
        "tag_object": tag_object,
        "verified_at": verified_at,
        "verifier_schema_version": 1,
        "workflow": workflow,
    }
    return f"{json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}\n"


def main() -> int:
    """Run version verification or extract release notes."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--version", required=True)

    notes_parser = subparsers.add_parser("notes")
    notes_parser.add_argument("--version", required=True)
    notes_parser.add_argument("--output", type=Path)

    release_parser = subparsers.add_parser("github-release")
    release_parser.add_argument("--version", required=True)
    release_parser.add_argument("--input", type=Path, required=True)
    release_parser.add_argument("--expected-state", choices=("draft", "public"))
    release_parser.add_argument("--expected-digests", type=Path)
    release_parser.add_argument("--refs-input", type=Path)
    release_parser.add_argument("--expected-sha")

    absence_parser = subparsers.add_parser("absence")
    absence_parser.add_argument("--input", type=Path, required=True)

    digest_parser = subparsers.add_parser("asset-digests")
    digest_parser.add_argument("--version", required=True)
    digest_parser.add_argument("--dist-dir", type=Path, required=True)
    digest_parser.add_argument("--output", type=Path, required=True)

    evidence_parser = subparsers.add_parser("evidence")
    evidence_parser.add_argument("--version", required=True)
    evidence_parser.add_argument("--release-input", type=Path, required=True)
    evidence_parser.add_argument("--refs-input", type=Path, required=True)
    evidence_parser.add_argument("--workflow-input", type=Path, required=True)
    evidence_parser.add_argument("--expected-sha", required=True)
    evidence_parser.add_argument("--expected-digests", type=Path, required=True)
    evidence_parser.add_argument("--verified-at", required=True)
    evidence_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "verify":
        verify_version(args.version)
        return 0
    if args.command == "github-release":
        expected_draft = None
        if args.expected_state is not None:
            expected_draft = args.expected_state == "draft"
        expected_digests = None
        if args.expected_digests is not None:
            expected_digests = _load_json_object(
                args.expected_digests.read_text(encoding="utf-8"),
                "expected asset digests",
            )
        verify_release_payload(
            args.input.read_text(encoding="utf-8"),
            args.version,
            expected_draft=expected_draft,
            expected_digests=expected_digests,
        )
        if (args.refs_input is None) != (args.expected_sha is None):
            raise ValueError("--refs-input and --expected-sha must be provided together")
        if args.refs_input is not None:
            verify_release_refs(args.refs_input.read_text(encoding="utf-8"), args.expected_sha)
        return 0
    if args.command == "absence":
        parse_release_absence(args.input.read_text(encoding="utf-8"))
        return 0
    if args.command == "asset-digests":
        digests = build_expected_asset_digests(args.dist_dir, args.version)
        args.output.write_text(
            f"{json.dumps(digests, sort_keys=True, separators=(',', ':'))}\n",
            encoding="utf-8",
        )
        return 0
    if args.command == "evidence":
        evidence = build_release_evidence(
            args.release_input.read_text(encoding="utf-8"),
            args.version,
            args.refs_input.read_text(encoding="utf-8"),
            args.workflow_input.read_text(encoding="utf-8"),
            expected_sha=args.expected_sha,
            expected_digests=_load_json_object(
                args.expected_digests.read_text(encoding="utf-8"),
                "expected asset digests",
            ),
            verified_at=args.verified_at,
        )
        args.output.write_text(evidence, encoding="utf-8")
        return 0

    notes = extract_release_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), args.version)
    if args.output is None:
        print(notes)
    else:
        args.output.write_text(f"{notes}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
