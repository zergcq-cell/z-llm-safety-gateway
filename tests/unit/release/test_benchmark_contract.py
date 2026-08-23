"""Performance report truthfulness contracts."""

from __future__ import annotations

from pathlib import Path

from tests.benchmarks import bench_pipeline
from tools.benchmark_report import render_comparison, render_report

LATENCY = {"p50": 0.0002, "p95": 0.0003, "p99": 0.0004, "n": 200}


def test_latency_only_report_marks_throughput_as_unrun() -> None:
    """TC-BENCH-001: latency-only reports never fabricate throughput."""
    report = render_report(LATENCY, None, "3.12.0", "Linux")
    assert "200 (latency), — (throughput)" in report
    assert "| req/s | — | >= 7128" in report
    assert "| req/s | 0 |" not in report


def test_throughput_only_report_marks_latency_as_unrun() -> None:
    """TC-BENCH-001: throughput-only reports never fabricate latency."""
    report = render_report(None, 2500.0, "3.12.0", "Linux")
    assert "— (latency), 50 warmup + 5 x 750 timed (throughput)" in report
    for percentile in ("P50", "P95", "P99"):
        assert f"| {percentile} | — |" in report
    assert "| P50 | 0.00ms |" not in report


def test_flow_foundation_report_uses_locked_change_gate() -> None:
    """TC-PE-003: the formal report never passes only the DESIGN floor."""
    below_gate = render_report(None, 7_127.0, "3.12.0", "Linux")
    at_gate = render_report(None, 7_128.0, "3.12.0", "Linux")

    assert "90% of 7920 Phase 2 baseline" in below_gate
    assert "| req/s | 7127 | >= 7128" in below_gate
    assert (
        "| req/s | 7127 | >= 7128 (90% of 7920 Phase 2 baseline) | "
        "BELOW TARGET |"
    ) in below_gate
    assert "| req/s | 7128 | >= 7128 (90% of 7920 Phase 2 baseline) | PASS |" in at_gate


def test_flow_foundation_report_uses_strict_p99_gate() -> None:
    """TC-PE-003: P99 must be strictly below 200ms."""
    below_gate = render_report({**LATENCY, "p99": 0.199}, None, "3.12.0", "Linux")
    at_gate = render_report({**LATENCY, "p99": 0.200_000}, None, "3.12.0", "Linux")

    assert "| P99 | 199.00ms | < 200.00ms | PASS |" in below_gate
    assert "| P99 | 200.00ms | < 200.00ms | BELOW TARGET |" in at_gate


def test_throughput_benchmark_warms_up_and_uses_best_of_five(monkeypatch) -> None:
    """TC-PE-003: the release runner uses the approved stable capacity method."""

    class FakeEngine:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, detectors, contexts, configs) -> None:
            self.calls += 1

    # Five elapsed trials: 1.0, 2.0, 0.5, 2.0, 1.0 seconds.
    timestamps = iter((0.0, 1.0, 2.0, 4.0, 5.0, 5.5, 6.0, 8.0, 9.0, 10.0))
    monkeypatch.setattr(bench_pipeline.time, "perf_counter", lambda: next(timestamps))
    engine = FakeEngine()

    throughput = bench_pipeline.bench_throughput(engine, [], {})

    assert throughput == bench_pipeline._THROUGHPUT_RUNS_PER_TRIAL / 0.5
    assert engine.calls == (
        bench_pipeline._WARMUP_RUNS
        + bench_pipeline._THROUGHPUT_TRIALS
        * bench_pipeline._THROUGHPUT_RUNS_PER_TRIAL
    )


def test_all_suite_comparison_records_v010_differences() -> None:
    """TC-BENCH-002: release report records comparable v0.1.0 deltas."""
    baseline = """\
| P50 | 0.20ms | 5.00ms | PASS |
| P95 | 0.40ms | 10.00ms | PASS |
| P99 | 0.50ms | 200.00ms | PASS |
| req/s | 2000 | 1000 | PASS |
"""
    comparison = render_comparison(LATENCY, 2500.0, baseline, "v0.1.0")
    assert "Comparison with v0.1.0" in comparison
    assert "| P50 latency | 0.20ms | 0.20ms | +0.0% |" in comparison
    assert "| Throughput | 2000 req/s | 2500 req/s | +25.0% |" in comparison


def test_formal_report_records_locked_gate_and_methodology() -> None:
    """TC-PE-003: the checked-in evidence uses the approved formal method."""
    report_path = (
        Path(__file__).resolve().parents[3]
        / "archive/2026-08-22-v0.2.0-flow-foundation/benchmark-report.md"
    )
    report = report_path.read_text(encoding="utf-8")

    assert "50 warmup + 5 x 750 timed (throughput)" in report
    assert ">= 7128 (90% of 7920 Phase 2 baseline)" in report
    assert "general DESIGN 14.3 floor (1000 req/s) is informational only" in report
    assert "best-of-five" in report
    assert "P99 uses all recorded latency samples" in report
