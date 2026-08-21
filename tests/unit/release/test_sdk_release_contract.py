"""Detector SDK release contracts."""

from __future__ import annotations

import re
from pathlib import Path

import z_llm_safety_gateway_sdk as sdk

ROOT = Path(__file__).resolve().parents[3]


def test_sdk_metadata_and_runtime_version_match_release() -> None:
    """TC-SDK-002: SDK metadata and runtime expose version 0.1.1."""
    metadata = (ROOT / "sdk" / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "0\.1\.1"$', metadata, re.MULTILINE)
    assert sdk.__version__ == "0.1.1"
