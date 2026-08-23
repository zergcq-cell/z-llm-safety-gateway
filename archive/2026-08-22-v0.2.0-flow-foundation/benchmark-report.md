# Performance Benchmark Report

- Date: 2026-08-22T17:31:58.163573+00:00
- Python: 3.10.20
- OS: Darwin
- Runs: 200 (latency), 50 warmup + 5 x 750 timed (throughput)
- Detector mix: rule-based only (prompt_injection, secret_leak, sensitive_words)

## Latency (end-to-end pipeline, rule-based only)

| Metric | Measured | Target (DESIGN 14.1) | Status |
|--------|----------|----------------------|--------|
| P50 | 0.12ms | <= 5.00ms | PASS |
| P95 | 0.13ms | <= 10.00ms | PASS |
| P99 | 0.15ms | < 200.00ms | PASS |

## Throughput (single instance, rule-based only)

| Metric | Measured | Flow Foundation locked target | Status |
|--------|----------|----------------------|--------|
| req/s | 8461 | >= 7128 (90% of 7920 Phase 2 baseline) | PASS |

## Change acceptance checks (REQ-PE-002)

| Check | Measured | Required | Status |
|-------|----------|----------|--------|
| P99 latency | 0.15ms | < 200ms | PASS |
| Throughput | 8461 req/s | >= 7128 req/s (90% of 7920 baseline) | PASS |
| Pending Flow tasks | 0 | 0 | PASS |
| Disabled observability | metrics/tracing disabled in TC-PE-003 | no exporter work | PASS |

## Notes

- Results are advisory for release review and are NOT enforced by CI.
- The general DESIGN 14.3 floor (1000 req/s) is informational only and cannot
  produce PASS for this change.
- Throughput uses an untimed warmup, five timed trials, and the best-of-five
  result; P99 uses all recorded latency samples.
- The benchmark uses a single connection; throughput scales with concurrency.
- `TC-PE-003` enforces the change-specific P99, throughput, disabled-observability,
  and pending-task acceptance checks.
- Below-target values should be recorded as differences for the release review.

## Comparison with v0.1.0

The acceptance gate is locked to the Phase 2 baseline of **7,920 req/s** and
P99 **0.16ms**. The table below uses a separate same-machine remeasurement
(8,028 req/s, P99 0.15ms) for descriptive comparison only; it does not change
the approved gate.

| Metric | Baseline | Current | Change |
|--------|----------|---------|--------|
| P50 latency | 0.13ms | 0.12ms | -6.3% |
| P95 latency | 0.14ms | 0.13ms | -8.8% |
| P99 latency | 0.15ms | 0.15ms | +1.5% |
| Throughput | 8028 req/s | 8461 req/s | +5.4% |

Positive latency change means slower; positive throughput change means faster.
Results are advisory and may vary by machine load.
