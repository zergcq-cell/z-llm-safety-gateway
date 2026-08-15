"""Pipeline performance benchmark (DESIGN.md Section 14.5).

Usage:
    python -m tests.benchmarks.bench_pipeline --suite latency
    python -m tests.benchmarks.bench_pipeline --suite throughput
    python -m tests.benchmarks.bench_pipeline --suite all

Measures end-to-end detection pipeline latency with rule-based detectors
only (no ML models) and compares against DESIGN.md Section 14 targets.
Output is a Markdown report; results are advisory for release review,
NOT enforced by CI (machine performance varies across environments).

Design targets (DESIGN.md 14.1/14.3):
    P50 rule-based only       < 5ms
    P95 rule-based only       < 10ms
    P99 any mix               < 200ms
    Throughput rule-based     1000 req/s (single instance)
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sdk" / "src"))

from z_llm_safety_gateway.detectors import create_default_registry  # noqa: E402
from z_llm_safety_gateway.models import DetectionContext  # noqa: E402

#: DESIGN.md 14.1 detection latency targets (rule-based only, seconds).
LATENCY_TARGETS = {
    "p50_rule_only": 0.005,
    "p95_rule_only": 0.010,
    "p99_any_mix": 0.200,
}

#: DESIGN.md 14.3 throughput targets (req/s, single instance).
THROUGHPUT_TARGETS = {
    "rule_based": 1000,
}

#: Number of detection runs per sample for stable statistics.
_N_RUNS = 200


def _build_engine() -> tuple[object, list[object], dict]:
    """Build a rule-based pipeline engine (3 input detectors, parallel)."""
    from z_llm_safety_gateway.pipeline.engine import PipelineEngine

    registry = create_default_registry()
    names = ["prompt_injection", "secret_leak", "sensitive_words"]
    detectors = []
    configs = {}
    for name in names:
        cls = registry.get(name)
        det = cls()
        configs[name] = {
            "priority": 1,
            "on_error": "fail_open",
            "timeout_seconds": 5.0,
            "words": ["urgent money transfer"],
            "count_block_threshold": 2,
        }
        detectors.append(det)
    engine = PipelineEngine()

    async def _init() -> None:
        for det in detectors:
            await det.initialize(configs[det.name])

    asyncio.run(_init())
    return engine, detectors, configs


def _sample_content(i: int) -> str:
    """Deterministic sample content for stable benchmarking."""
    return (
        f"Sample request {i}: could you explain the water cycle in simple terms "
        "for a school project? Also what is the capital of France?"
    )


def bench_latency(engine: object, detectors: list[object], configs: dict) -> dict:
    """Measure end-to-end pipeline latency (seconds) per detection."""
    ctx = DetectionContext(direction="input", request_id="bench")
    samples = [_sample_content(i) for i in range(_N_RUNS)]

    async def _run_all() -> list[float]:
        latencies: list[float] = []
        for _ in samples:
            start = time.perf_counter()
            await engine.run(detectors, [ctx], configs)
            latencies.append(time.perf_counter() - start)
        return latencies

    latencies = asyncio.run(_run_all())
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    return {
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "mean": statistics.fmean(latencies),
        "n": len(latencies),
    }


def bench_throughput(engine: object, detectors: list[object], configs: dict) -> float:
    """Measure single-connection throughput (detections per second)."""
    ctx = DetectionContext(direction="input", request_id="bench")

    async def _run_batch(n: int) -> float:
        start = time.perf_counter()
        for _ in range(n):
            await engine.run(detectors, [ctx], configs)
        elapsed = time.perf_counter() - start
        return n / elapsed

    return asyncio.run(_run_batch(500))


def _fmt_seconds(seconds: float) -> str:
    return f"{seconds * 1000:.2f}ms"


def render_report(
    lat: dict, throughput: float, python_version: str, os_name: str
) -> str:
    """Render a Markdown report comparing results against DESIGN 14 targets."""
    lines = [
        "# Performance Benchmark Report",
        "",
        f"- Date: {datetime.now(timezone.utc).isoformat()}",
        f"- Python: {python_version}",
        f"- OS: {os_name}",
        f"- Runs: {lat['n']} (latency), 500 (throughput)",
        "- Detector mix: rule-based only (prompt_injection, secret_leak, sensitive_words)",
        "",
        "## Latency (end-to-end pipeline, rule-based only)",
        "",
        "| Metric | Measured | Target (DESIGN 14.1) | Status |",
        "|--------|----------|----------------------|--------|",
    ]
    rows = [
        ("P50", lat["p50"], LATENCY_TARGETS["p50_rule_only"]),
        ("P95", lat["p95"], LATENCY_TARGETS["p95_rule_only"]),
        ("P99", lat["p99"], LATENCY_TARGETS["p99_any_mix"]),
    ]
    for label, measured, target in rows:
        status = "PASS" if measured <= target else "BELOW TARGET"
        lines.append(
            f"| {label} | {_fmt_seconds(measured)} | {_fmt_seconds(target)} | {status} |"
        )
    lines += [
        "",
        "## Throughput (single instance, rule-based only)",
        "",
        "| Metric | Measured | Target (DESIGN 14.3) | Status |",
        "|--------|----------|----------------------|--------|",
        f"| req/s | {throughput:.0f} | {THROUGHPUT_TARGETS['rule_based']} | "
        f"{'PASS' if throughput >= THROUGHPUT_TARGETS['rule_based'] else 'BELOW TARGET'} |",
        "",
        "## Notes",
        "",
        "- Results are advisory for release review and are NOT enforced by CI.",
        "- The benchmark uses a single connection; throughput scales with concurrency.",
        "- Below-target values should be recorded as differences for the release review.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline performance benchmark")
    parser.add_argument(
        "--suite",
        choices=["latency", "throughput", "all"],
        default="all",
        help="benchmark suite to run",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="write report to this Markdown file (default: tests/benchmarks/results/<date>.md)",
    )
    args = parser.parse_args()

    engine, detectors, configs = _build_engine()
    import platform

    lat = None
    throughput = None
    if args.suite in ("latency", "all"):
        lat = bench_latency(engine, detectors, configs)
        print(f"Latency: P50={_fmt_seconds(lat['p50'])} P95={_fmt_seconds(lat['p95'])} "
              f"P99={_fmt_seconds(lat['p99'])}")
    if args.suite in ("throughput", "all"):
        throughput = bench_throughput(engine, detectors, configs)
        print(f"Throughput: {throughput:.0f} req/s")

    if lat is not None or throughput is not None:
        report = render_report(
            lat or {"p50": 0, "p95": 0, "p99": 0, "n": 0},
            throughput or 0.0,
            platform.python_version(),
            platform.system(),
        )
        out = args.output or (
            Path(__file__).parent / "results"
            / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"Report written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
