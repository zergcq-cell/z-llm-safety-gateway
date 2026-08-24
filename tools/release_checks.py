#!/usr/bin/env python3
"""Deterministic local checks shared by release CI and tests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def verify_release_payload(payload: str, version: str) -> None:
    """Verify exact GitHub Release tag, notes, and independent-version assets."""
    loaded = json.loads(payload)
    if not isinstance(loaded, dict):
        raise ValueError("GitHub Release payload must be an object")

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

    sdk_version = _declared_version(ROOT / "sdk" / "pyproject.toml", "version")
    expected_assets = sorted(
        [
            f"z_llm_safety_gateway-{normalized}-py3-none-any.whl",
            f"z_llm_safety_gateway-{normalized}.tar.gz",
            f"z_llm_safety_gateway_sdk-{sdk_version}-py3-none-any.whl",
            f"z_llm_safety_gateway_sdk-{sdk_version}.tar.gz",
        ]
    )
    asset_entries = loaded.get("assets")
    if not isinstance(asset_entries, list):
        raise ValueError("GitHub Release assets must be a list")
    actual_assets: list[str] = []
    for entry in asset_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise ValueError("GitHub Release asset is missing a name")
        actual_assets.append(entry["name"])
    if sorted(actual_assets) != expected_assets:
        raise ValueError(
            f"GitHub Release assets mismatch: expected {expected_assets}, "
            f"found {sorted(actual_assets)}"
        )


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

    args = parser.parse_args()
    if args.command == "verify":
        verify_version(args.version)
        return 0
    if args.command == "github-release":
        verify_release_payload(args.input.read_text(encoding="utf-8"), args.version)
        return 0

    notes = extract_release_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), args.version)
    if args.output is None:
        print(notes)
    else:
        args.output.write_text(f"{notes}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
