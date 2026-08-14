"""zlg CLI — plugin/detector management (DESIGN.md Section 7.6.3).

Subcommands:
- ``zlg detectors list [--enabled]`` — list available detectors
- ``zlg detectors info <name>`` — show detector details
- ``zlg detectors test <name> --input <text>`` — run detection on sample input
- ``zlg detectors check-connection <name>`` — validate a gRPC sidecar connection
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.detectors.registry import DetectorRegistry
from z_llm_safety_gateway.plugins.loader import load_plugins


def _build_registry() -> DetectorRegistry:
    """Create the default registry with built-ins + entry-point plugins."""
    registry = create_default_registry()
    load_plugins(registry)
    return registry


def _build_grpc_detector(config: dict[str, Any]) -> Any:
    """Build a GRPCDetector for connection checks."""
    from z_llm_safety_gateway.plugins.grpc.client import GRPCDetector

    return GRPCDetector()


def _cmd_list(args: argparse.Namespace, registry: DetectorRegistry) -> int:
    names = registry.list()
    if args.enabled:
        # Filter to detectors enabled in the gateway config (TC-CLI-001b).
        try:
            config = load_config(args.config)
        except Exception as exc:
            print(f"Failed to load config: {exc}", file=sys.stderr)
            return 1
        enabled: set[str] = set()
        detectors_cfg = config.pipeline.detectors
        from z_llm_safety_gateway.config.models import DetectorsConfig

        if isinstance(detectors_cfg, DetectorsConfig):
            for det in list(detectors_cfg.input) + list(detectors_cfg.output):
                if det.enabled:
                    enabled.add(det.name)
        names = [n for n in names if n in enabled]
    for name in sorted(names):
        print(name)
    return 0


def _cmd_info(args: argparse.Namespace, registry: DetectorRegistry) -> int:
    try:
        cls = registry.get(args.name)
    except KeyError:
        print(f"Unknown detector: {args.name}", file=sys.stderr)
        return 1
    print(f"name:        {cls.name}")
    print(f"category:    {cls.category}")
    print(f"description: {cls.description}")
    print(f"version:     {cls.version}")
    return 0


def _cmd_test(args: argparse.Namespace, registry: DetectorRegistry) -> int:
    try:
        cls = registry.get(args.name)
    except KeyError:
        print(f"Unknown detector: {args.name}", file=sys.stderr)
        return 1

    from z_llm_safety_gateway.models import DetectionContext

    detector = cls()

    async def _run() -> int:
        await detector.initialize({})
        result = await detector.detect(
            args.input,
            DetectionContext(direction="input", request_id="zlg-cli-test"),
        )
        print(f"action:      {result.action}")
        print(f"risk_level:  {result.risk_level}")
        print(f"confidence:  {result.confidence:.3f}")
        print(f"message:     {result.message}")
        return 0

    return asyncio.run(_run())


def _cmd_check_connection(args: argparse.Namespace, registry: DetectorRegistry) -> int:
    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 1

    detector_cfg = None
    detectors_cfg = config.pipeline.detectors
    from z_llm_safety_gateway.config.models import DetectorsConfig

    if not isinstance(detectors_cfg, DetectorsConfig):
        print(
            f"Detector '{args.name}' not found or not type=grpc in config",
            file=sys.stderr,
        )
        return 1
    for det in list(detectors_cfg.input) + list(detectors_cfg.output):
        if det.name == args.name and det.type == "grpc":
            detector_cfg = det
            break
    if detector_cfg is None:
        print(
            f"Detector '{args.name}' not found or not type=grpc in config",
            file=sys.stderr,
        )
        return 1

    det = _build_grpc_detector(detector_cfg.config)

    async def _run() -> int:
        try:
            await det.initialize(detector_cfg.config)
            healthy = await det.health_check()
        except Exception as exc:
            print(f"Connection failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await det.shutdown()
        if healthy:
            print("status: serving")
            return 0
        print("status: not_serving", file=sys.stderr)
        return 1

    return asyncio.run(_run())


def build_parser() -> argparse.ArgumentParser:
    """Build the zlg argument parser."""
    parser = argparse.ArgumentParser(prog="zlg", description="z LLM Safety Gateway CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    det = sub.add_parser("detectors", help="detector/plugin management")
    det_sub = det.add_subparsers(dest="action", required=True)

    p_list = det_sub.add_parser("list", help="list detectors")
    p_list.add_argument("--enabled", action="store_true", help="only enabled detectors")
    p_list.add_argument(
        "--config",
        default="config/gateway.yaml",
        help="path to gateway config for --enabled (default: config/gateway.yaml)",
    )
    p_list.set_defaults(handler=_cmd_list)

    p_info = det_sub.add_parser("info", help="show detector details")
    p_info.add_argument("name")
    p_info.set_defaults(handler=_cmd_info)

    p_test = det_sub.add_parser("test", help="run detection on sample input")
    p_test.add_argument("name")
    p_test.add_argument("--input", required=True)
    p_test.set_defaults(handler=_cmd_test)

    p_conn = det_sub.add_parser("check-connection", help="validate gRPC sidecar")
    p_conn.add_argument("name")
    p_conn.add_argument(
        "--config",
        default="config/gateway.yaml",
        help="path to gateway config (default: config/gateway.yaml)",
    )
    p_conn.set_defaults(handler=_cmd_check_connection)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (console script ``zlg``)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    registry = _build_registry()
    return int(handler(args, registry))


if __name__ == "__main__":
    raise SystemExit(main())
