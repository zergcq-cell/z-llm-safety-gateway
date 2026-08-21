#!/usr/bin/env python3
"""Deterministic local checks shared by release CI and tests."""

from __future__ import annotations

import argparse
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
    declared = {
        _declared_version(ROOT / "pyproject.toml", "version"),
        _declared_version(ROOT / "src" / "z_llm_safety_gateway" / "__init__.py", "__version__"),
        _declared_version(ROOT / "sdk" / "pyproject.toml", "version"),
        _declared_version(
            ROOT / "sdk" / "src" / "z_llm_safety_gateway_sdk" / "__init__.py",
            "__version__",
        ),
    }
    if declared != {normalized}:
        raise ValueError(f"version mismatch: expected {normalized}, found {sorted(declared)}")
    extract_release_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), normalized)


def main() -> int:
    """Run version verification or extract release notes."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--version", required=True)

    notes_parser = subparsers.add_parser("notes")
    notes_parser.add_argument("--version", required=True)
    notes_parser.add_argument("--output", type=Path)

    args = parser.parse_args()
    if args.command == "verify":
        verify_version(args.version)
        return 0

    notes = extract_release_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), args.version)
    if args.output is None:
        print(notes)
    else:
        args.output.write_text(f"{notes}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
