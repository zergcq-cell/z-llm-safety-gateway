# Technical Design — Provider 扩展

## Context

现有 Provider 通过 `Provider` 抽象、router 和统一 HTTP/SSE 响应契约执行。Anthropic 与 Gemini 的认证头、请求 envelope、响应候选结构和流式事件不同，需要在 adapter 边界转换，不能让 Flow 或核心了解 Provider 细节。

## Project Principle Check

1. Provider-specific conversion remains in plugins; Flow only composes capabilities and core owns lifecycle/contracts.
2. Timeout, cancellation, rate limit, upstream failure and no-retry behavior are explicit reason-coded outcomes.
3. Public HTTP/SSE and error contracts remain stable; adapters bound conversion cost and upstream deadlines.
4. Audit records provider/model/tenant scope and reason codes only; secrets and raw content are redacted.

## Decisions

### D1 — Adapter per Provider

Implement `AnthropicProvider` and `GeminiProvider` behind the existing base contract. This isolates API drift and keeps the router declarative. A generic translation layer was rejected because message and streaming semantics are materially different.

### D2 — Explicit translators

Use provider-local request and response translators with validation for unsupported fields. Silent field dropping is rejected; unsupported combinations return a stable provider error.

### D3 — Unified streaming normalization

Translate provider events to the existing gateway SSE event model, preserving ordering, terminal `[DONE]`, cancellation and mid-stream error behavior. Exposing native events was rejected because it breaks client compatibility.

### D4 — Existing failure policy

Reuse current timeout, cancellation, 4xx/429/5xx mapping and no-retry policy. Provider-specific status and request IDs may appear only in sanitized details.

### D5 — Tenant snapshot routing

Resolve adapter and credentials from the frozen tenant provider snapshot for each request. No cross-tenant fallback or shared mutable credential state is introduced.

## Architecture

```text
Request → tenant snapshot → ProviderRouter
                         ├─ AnthropicProvider → translate → Claude API
                         ├─ GeminiProvider    → translate → Gemini API
                         └─ existing adapters
Claude/Gemini response → normalize → gateway HTTP/SSE → post-audit
```

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| message/tool field loss | field matrix and unsupported-field tests |
| stream ordering drift | deterministic fixture streams and terminal-event assertions |
| credential or tenant leakage | snapshot isolation and redaction tests |
| upstream API evolution | versioned adapter boundaries and explicit config |

