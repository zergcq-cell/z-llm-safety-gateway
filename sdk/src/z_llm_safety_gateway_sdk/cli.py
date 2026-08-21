"""zlg-sdk CLI — detector scaffolding (DESIGN.md Section 7.4.3).

Subcommands:
- ``zlg-sdk new <name> --type python|grpc [--language python|go]`` — scaffold
- ``zlg-sdk validate <path>`` — validate a detector implementation
- ``zlg-sdk test <path>`` — run detector tests (delegates to pytest)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

#: Detector interface attributes required for validation.
_REQUIRED_ATTRS = ("name", "category", "description", "version")
_REQUIRED_METHODS = ("initialize", "detect")

#: Entry point group used in generated pyproject.toml.
ENTRY_POINT_GROUP = "z_llm_safety_gateway.detectors"
SDK_RELEASE_DEPENDENCY = (
    "z-llm-safety-gateway-sdk @ "
    "https://github.com/zergcq-cell/z-llm-safety-gateway/releases/download/"
    "v0.1.1/z_llm_safety_gateway_sdk-0.1.1-py3-none-any.whl"
)


def _snake(name: str) -> str:
    """Convert a project name like 'my-detector' to 'my_detector'."""
    return name.replace("-", "_")


def _cmd_new(args: argparse.Namespace) -> int:
    """Scaffold a new detector project (TC-SDK-003/004)."""
    proj_dir = Path(args.name)
    pkg = _snake(Path(args.name).name)
    src_dir = proj_dir / "src" / pkg
    src_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "tests").mkdir(parents=True, exist_ok=True)

    entry_point_name = _snake(Path(args.name).name)
    pyproject = f'''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{args.name}"
version = "0.1.0"
description = "A safety detector for the z LLM Safety Gateway"
requires-python = ">=3.10"
dependencies = ["{SDK_RELEASE_DEPENDENCY}"]

[project.entry-points."{ENTRY_POINT_GROUP}"]
{entry_point_name} = "{pkg}.detector:{_camel(entry_point_name)}Detector"

[tool.hatch.build.targets.wheel]
packages = ["src/{pkg}"]

[tool.hatch.metadata]
allow-direct-references = true
'''
    (proj_dir / "pyproject.toml").write_text(pyproject)

    (src_dir / "__init__.py").write_text(f'"""Detector package: {args.name}."""\n')

    if args.type == "grpc":
        detector_src = _GRPC_DETECTOR_TEMPLATE.format(pkg=pkg, name=entry_point_name)
        (src_dir / "server.py").write_text(
            f'"""gRPC sidecar server for {args.name} (DESIGN.md Section 7.3)."""\n'
            "# Implement DetectorService per proto/detector/v1/detector.proto.\n"
        )
        proto_dir = src_dir / "proto" / "detector" / "v1"
        proto_dir.mkdir(parents=True, exist_ok=True)
        (proto_dir / "detector.proto").write_text(
            "# Place the detector.proto contract here (see gateway proto/).\n"
        )
    else:
        detector_src = _PYTHON_DETECTOR_TEMPLATE.format(
            pkg=pkg, cls=_camel(entry_point_name) + "Detector", name=entry_point_name
        )
    (src_dir / "detector.py").write_text(detector_src)

    (proj_dir / "tests" / "test_detector.py").write_text(
        _TEST_TEMPLATE.format(cls=_camel(entry_point_name) + "Detector", pkg=pkg)
    )
    print(f"Created detector project at {proj_dir}")
    return 0


def _camel(name: str) -> str:
    """Convert 'my_detector' to 'MyDetector'."""
    return "".join(part.capitalize() for part in name.split("_"))


def validate_detector_module(path: Path) -> int:
    """Validate that a module defines a proper Detector implementation.

    Args:
        path: Path to the detector module (.py).

    Returns:
        0 on success, 1 on validation failure.
    """
    import importlib.util

    if not path.is_file():
        print(f"Not a file: {path}", file=sys.stderr)
        return 1
    try:
        module_name = f"_zlg_sdk_validate_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            print(f"Cannot load module: {path}", file=sys.stderr)
            return 1
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    candidates = [
        getattr(module, name)
        for name in dir(module)
        if isinstance(getattr(module, name), type)
    ]
    detector_cls = None
    for cls in candidates:
        if cls is type:
            continue
        if all(hasattr(cls, a) for a in _REQUIRED_ATTRS) and all(
            callable(getattr(cls, m, None)) for m in _REQUIRED_METHODS
        ):
            detector_cls = cls
            break
    if detector_cls is None:
        print(
            "No Detector implementation found (expected name/category/description/"
            "version attrs + async initialize/detect methods)",
            file=sys.stderr,
        )
        return 1
    print(f"Valid detector: {detector_cls.__name__}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    target = Path(args.path)
    module = (
        target / "src" / _snake(target.name) / "detector.py"
        if target.is_dir()
        else target
    )
    return validate_detector_module(module)


def _cmd_test(args: argparse.Namespace) -> int:
    """Run tests in the detector project via pytest."""
    return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=args.path)


def build_parser() -> argparse.ArgumentParser:
    """Build the zlg-sdk argument parser."""
    parser = argparse.ArgumentParser(
        prog="zlg-sdk", description="z LLM Safety Gateway Detector SDK CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new detector project")
    p_new.add_argument("name")
    p_new.add_argument("--type", choices=["python", "grpc"], default="python")
    p_new.add_argument("--language", choices=["python", "go"], default="python")
    p_new.set_defaults(handler=_cmd_new)

    p_val = sub.add_parser("validate", help="validate a detector implementation")
    p_val.add_argument("path")
    p_val.set_defaults(handler=_cmd_validate)

    p_test = sub.add_parser("test", help="run detector project tests")
    p_test.add_argument("path")
    p_test.set_defaults(handler=_cmd_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (console script ``zlg-sdk``)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = cast(Callable[[argparse.Namespace], int], args.handler)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
_PYTHON_DETECTOR_TEMPLATE = '''\
"""Detector implementation for {name} (z LLM Safety Gateway)."""

from z_llm_safety_gateway_sdk import Detector, DetectionContext, DetectionResult


class {cls}(Detector):
    """A safety detector."""

    name = "{name}"
    category = "custom"
    description = "My custom safety detector"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        """Load configuration (thresholds, paths, keys)."""
        self.block_threshold = config.get("block_threshold", 0.85)

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        """Run detection on content."""
        # Implement detection logic here.
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="Passed",
        )
'''

_GRPC_DETECTOR_TEMPLATE = """\
# gRPC sidecar detector placeholder.
# Implement DetectorService per proto/detector/v1/detector.proto and
# serve via the z_llm_safety_gateway_sdk grpc server template.
"""

_TEST_TEMPLATE = '''\
"""Tests for {cls}."""

import pytest

from {pkg}.detector import {cls}


@pytest.mark.asyncio
async def test_detector_allows_safe_content():
    detector = {cls}()
    await detector.initialize({{}})
    from z_llm_safety_gateway_sdk.testing import make_context, assert_allowed

    result = await detector.detect("hello world", make_context())
    assert_allowed(result)
'''
