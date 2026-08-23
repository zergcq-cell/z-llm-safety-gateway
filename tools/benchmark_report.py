"""Lightweight, deterministic Markdown rendering for performance benchmarks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone

LATENCY_TARGETS = {
    "p50_rule_only": 0.005,
    "p95_rule_only": 0.010,
    "p99_any_mix": 0.200,
}
DESIGN_THROUGHPUT_FLOOR = 1_000
PHASE_2_THROUGHPUT_BASELINE = 7_920
FLOW_FOUNDATION_THROUGHPUT_TARGET = PHASE_2_THROUGHPUT_BASELINE * 90 // 100
THROUGHPUT_METHOD = "50 warmup + 5 x 750 timed"


def format_seconds(seconds: float) -> str:
    """Format seconds as milliseconds for release reports."""
    return f"{seconds * 1000:.2f}ms"


def render_report(
    lat: Mapping[str, float | int] | None,
    throughput: float | None,
    python_version: str,
    os_name: str,
) -> str:
    """Render a truthful report; unrun suites use an em dash, never zero."""
    lat_runs = str(lat["n"]) if lat is not None else "—"
    tp_runs = THROUGHPUT_METHOD if throughput is not None else "—"
    lines = [
        "# Performance Benchmark Report",
        "",
        f"- Date: {datetime.now(timezone.utc).isoformat()}",
        f"- Python: {python_version}",
        f"- OS: {os_name}",
        f"- Runs: {lat_runs} (latency), {tp_runs} (throughput)",
        "- Detector mix: rule-based only (prompt_injection, secret_leak, sensitive_words)",
        "",
        "## Latency (end-to-end pipeline, rule-based only)",
        "",
        "| Metric | Measured | Target (DESIGN 14.1) | Status |",
        "|--------|----------|----------------------|--------|",
    ]
    rows = [
        (
            "P50",
            None if lat is None else float(lat["p50"]),
            LATENCY_TARGETS["p50_rule_only"],
            False,
        ),
        (
            "P95",
            None if lat is None else float(lat["p95"]),
            LATENCY_TARGETS["p95_rule_only"],
            False,
        ),
        (
            "P99",
            None if lat is None else float(lat["p99"]),
            LATENCY_TARGETS["p99_any_mix"],
            True,
        ),
    ]
    for label, measured, target, strict in rows:
        if measured is None:
            status = "—"
            measured_str = "—"
        else:
            meets_target = measured < target if strict else measured <= target
            status = "PASS" if meets_target else "BELOW TARGET"
            measured_str = format_seconds(measured)
        target_operator = "<" if strict else "<="
        lines.append(
            f"| {label} | {measured_str} | {target_operator} "
            f"{format_seconds(target)} | {status} |"
        )

    if throughput is None:
        tp_str = "—"
        tp_status = "—"
    else:
        tp_str = f"{throughput:.0f}"
        tp_status = (
            "PASS"
            if throughput >= FLOW_FOUNDATION_THROUGHPUT_TARGET
            else "BELOW TARGET"
        )
    lines += [
        "",
        "## Throughput (single instance, rule-based only)",
        "",
        "| Metric | Measured | Flow Foundation locked target | Status |",
        "|--------|----------|----------------------|--------|",
        f"| req/s | {tp_str} | >= {FLOW_FOUNDATION_THROUGHPUT_TARGET} "
        f"(90% of {PHASE_2_THROUGHPUT_BASELINE} Phase 2 baseline) | {tp_status} |",
        "",
        "## Notes",
        "",
        "- Results are advisory for release review and are NOT enforced by CI.",
        f"- The general DESIGN 14.3 floor ({DESIGN_THROUGHPUT_FLOOR} req/s) is "
        "informational only and cannot produce PASS for this change.",
        "- Throughput uses an untimed warmup, five timed trials, and the "
        "best-of-five result; P99 uses all recorded latency samples.",
        "- The benchmark uses a single connection; throughput scales with concurrency.",
        "- Below-target values should be recorded as differences for the release review.",
        "",
    ]
    return "\n".join(lines)


def _baseline_metric(report: str, label: str, unit: str = "") -> float:
    pattern = rf"^\| {re.escape(label)} \| (?P<value>[0-9.]+){re.escape(unit)} \|"
    match = re.search(pattern, report, re.MULTILINE)
    if match is None:
        raise ValueError(f"baseline report is missing {label}")
    return float(match.group("value"))


def _change(current: float, baseline: float) -> str:
    return f"{((current / baseline) - 1) * 100:+.1f}%"


def render_comparison(
    lat: Mapping[str, float | int],
    throughput: float,
    baseline_report: str,
    baseline_version: str,
) -> str:
    """Compare an all-suite run with a prior report using like-for-like metrics."""
    baseline_latency = {
        label: _baseline_metric(baseline_report, label, "ms") for label in ("P50", "P95", "P99")
    }
    baseline_throughput = _baseline_metric(baseline_report, "req/s")
    lines = [
        f"## Comparison with {baseline_version}",
        "",
        "| Metric | Baseline | Current | Change |",
        "|--------|----------|---------|--------|",
    ]
    for label, key in (("P50", "p50"), ("P95", "p95"), ("P99", "p99")):
        current_ms = float(lat[key]) * 1000
        baseline_ms = baseline_latency[label]
        lines.append(
            f"| {label} latency | {baseline_ms:.2f}ms | {current_ms:.2f}ms | "
            f"{_change(current_ms, baseline_ms)} |"
        )
    lines.append(
        f"| Throughput | {baseline_throughput:.0f} req/s | {throughput:.0f} req/s | "
        f"{_change(throughput, baseline_throughput)} |"
    )
    lines += [
        "",
        "Positive latency change means slower; positive throughput change means faster.",
        "Results are advisory and may vary by machine load.",
        "",
    ]
    return "\n".join(lines)
