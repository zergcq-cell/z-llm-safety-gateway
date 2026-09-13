# Test Plan — Provider 扩展

## Strategy

Unit tests cover translators, config and error mapping; integration tests use deterministic HTTP mocks for non-streaming and SSE; regression tests cover existing providers and tenant routing. No live provider credentials are used.

## Test Cases

| ID | Scenario | Priority |
|---|---|---|
| TC-APA-001 | Claude request maps system/messages/model and auth header | P0 |
| TC-APA-002 | Claude response and stream normalize to gateway contract | P0 |
| TC-GPA-001 | Gemini request maps contents/model and auth | P0 |
| TC-GPA-002 | Gemini response and stream normalize to gateway contract | P0 |
| TC-PFC-001 | Unsupported fields fail explicitly without silent loss | P0 |
| TC-PFC-002 | 4xx/429/5xx/network/timeout/cancel map to stable errors | P0 |
| TC-ROUTE-001 | Tenant snapshot selects only its configured adapter/credential | P0 |
| TC-SSE-001 | Mid-stream error emits error event then `[DONE]` | P0 |
| TC-COMP-001 | `/v1/models` behavior is deterministic for new providers | P1 |
| TC-COMP-002 | Existing OpenAI/Azure/compatible provider regression | P0 |
| TC-PRIV-001 | Secrets, raw content and raw exceptions are redacted | P0 |

## Execution Matrix

| Area | Unit | Integration | Regression |
|---|---:|---:|---:|
| translators | ✓ | ✓ |  |
| streaming/errors | ✓ | ✓ | ✓ |
| tenant routing | ✓ | ✓ | ✓ |
| existing providers |  |  | ✓ |
| privacy | ✓ | ✓ | ✓ |

## Regression Risks

High: router/config, SSE normalization, error mapping. Medium: models endpoint and metrics labels. Low: documentation-only changes.

## Order

P0 focused RED tests → adapter implementation → full provider regression → Ruff/mypy/full suite.

