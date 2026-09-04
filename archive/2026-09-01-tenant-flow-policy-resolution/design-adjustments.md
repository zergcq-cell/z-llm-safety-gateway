# Design Adjustments — tenant-flow-policy-resolution

Phase 5 made five bounded adjustments. None changes the Gate 2 scope or requires re-specification.

1. Complete tenant runtime bundles are now validated at startup and again during request resolution. An incomplete tenant bundle returns the stable 503 boundary and never enters the global router or pipeline.
2. Tenant readiness refreshes all policy-local status registries under bounded concurrency and a five-second aggregate deadline, exposes details only for the request tenant, and fails closed on any application-wide strict issue. Lifecycle audit/metrics include the bounded policy ID so same-named Detectors cannot overwrite one another; declared circuit breakers compile into policy-private runtime state.
3. Detector configuration snapshots are recursively immutable; API and Provider credentials are hidden from model representations; routine Detector initialization logs retain only bounded summaries.
4. Buffer-mode SSE now reassembles complete SSE events before extracting output text, covering network chunks that contain multiple events.
5. The test configuration narrowly ignores Starlette's AnyIO `BlockingPortal` compatibility warning on Python 3.10/3.11 while continuing to fail on every other `DeprecationWarning`.

These adjustments reinforce all four project principles. They keep tenant behavior outside Flow core, make failures explicit, preserve HTTP/SSE and legacy contracts, and improve evidence/data protection. The only process exception is that S7's original Phase 4 RED result was not recorded at the time; this gap is disclosed rather than reconstructed. All Phase 5 corrections have observed RED and GREEN evidence.
