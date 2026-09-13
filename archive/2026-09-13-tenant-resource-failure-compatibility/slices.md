# Change 4 切片执行计划

## Dependency Graph Summary

```text
S1 ResourceBudget + tenant gate
          │
          ├── S2 lease lifecycle + cancellation
          │          │
          │          ├── S3 unified failure matrix + deadline
          │          │          │
          │          │          └── S4 Provider/SSE/post-audit integration
          │          │
          │          └──────────────────────────────┐
          └─────────────────────────────────────────┴── S5 legacy + v0.3 aggregate acceptance
```

CLI dependency graph unavailable because system Python lacks PyYAML; dependencies were reviewed manually. Shared workspace requires serial execution.

## Slice Execution Plan

| Slice | Scope | TC | Risk | Effort | Parallel | Rationale |
|---|---|---:|---:|---:|---|---|
| S1 | ResourceBudget schema, limits, tenant gate and bounded queue | TRI-001, TRI-003 | 5 | L | serial | Establishes all downstream resource contracts |
| S2 | Lease release, cancellation and active-count lifecycle | TRI-002 | 4 | M | serial | Depends on S1 gate |
| S3 | FailureOutcome, reason codes, deadline and retry policy | TFM-001, TFM-002, TFM-003 | 5 | L | serial | Depends on lease and budget semantics |
| S4 | Provider, sync/async/SSE/buffer/post-audit propagation | TFM-003 | 5 | L | serial | Integrates runtime paths after core contracts |
| S5 | Legacy compatibility and v0.3 aggregate matrix | V03-001, V03-002 | 4 | L | serial | Final acceptance depends on all preceding slices |

## Rationale

S1/S2 form the minimal resource substrate. S3 makes all failures explicit before production path wiring. S4 closes long-lived and background lifecycle gaps. S5 proves the five goals across the three delivered changes and preserves legacy behavior.
