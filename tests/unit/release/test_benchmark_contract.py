"""Performance report truthfulness contracts."""

from __future__ import annotations

from tools.benchmark_report import render_comparison, render_report

LATENCY = {"p50": 0.0002, "p95": 0.0003, "p99": 0.0004, "n": 200}


def test_latency_only_report_marks_throughput_as_unrun() -> None:
    """TC-BENCH-001: latency-only reports never fabricate throughput."""
    report = render_report(LATENCY, None, "3.12.0", "Linux")
    assert "200 (latency), — (throughput)" in report
    assert "| req/s | — | 1000 | — |" in report
    assert "| req/s | 0 |" not in report


def test_throughput_only_report_marks_latency_as_unrun() -> None:
    """TC-BENCH-001: throughput-only reports never fabricate latency."""
    report = render_report(None, 2500.0, "3.12.0", "Linux")
    assert "— (latency), 500 (throughput)" in report
    for percentile in ("P50", "P95", "P99"):
        assert f"| {percentile} | — |" in report
    assert "| P50 | 0.00ms |" not in report


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
