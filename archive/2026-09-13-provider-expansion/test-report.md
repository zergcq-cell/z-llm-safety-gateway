# Test Report — Provider 扩展

## Overall

- Focused adapter, tenant-routing and model-endpoint tests: **19 passed**
- Full regression excluding sandbox-only gRPC port tests and host-sensitive throughput test: **1214 passed, 1 skipped**
- Ruff: passed
- mypy: passed (101 source files)

## Coverage Mapping

Anthropic and Gemini request/response conversion, system messages, text content validation,
function tools/calls/results and tool choice, finish reasons, rate-limit error sanitization,
auth headers, streaming normalization, model discovery authentication, tenant routing isolation,
router registration, existing-provider regression, validation and documentation compatibility
are automated.

## Environment Signals

The excluded gRPC tests require local port binding, which is denied by the execution sandbox. The throughput benchmark is host-scheduler sensitive and ran below its historical threshold once; no provider-related regression was observed.

## Failure Mode Review

No new hallucinated paths, silent fallback, credential exposure, contract gap or cross-tenant routing issue found. Adjustments ADJ-001 and ADJ-002 are compatibility clarifications and do not require re-specification.

## Principle Recheck

Provider-specific behavior remains in adapters, failure behavior is explicit, HTTP/SSE contracts remain stable, and evidence/logging paths do not receive secrets or raw content.

## Conclusion

Implementation and quality gates pass for the scoped Change 5 behavior. A previous premature
completion claim was withdrawn; this report records the replacement verification. Ready for a
fresh Gate 3 confirmation; delivery will archive the change and record the v0.4.0 roadmap assignment.
