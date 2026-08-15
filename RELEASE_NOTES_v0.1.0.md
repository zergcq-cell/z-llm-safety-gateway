# v0.1.0 — First Public Test Release

**Release date:** 2026-08-15

This is the first public test release of **z LLM Safety Gateway** — an open-source, modular content safety gateway that acts as a transparent proxy between your application and LLM providers, performing real-time safety detection and filtering.

> **Versioning note:** Per our SemVer-aligned policy, `v0.0.1`–`v0.0.6` were internal development phases; **`v0.1.0` is the first public test release** (API may evolve). We will move to `v1.0.0` (general availability) once the API is validated in real-world use.

---

## Highlights

- **Transparent LLM proxy** — OpenAI-compatible `/v1/chat/completions`, `/v1/models`; routes to OpenAI, Azure, and OpenAI-compatible providers (e.g. Ollama)
- **5 built-in detectors** — prompt injection, PII redaction, toxicity (ML), sensitive words, secret leak — executed in parallel with configurable thresholds
- **Streaming safety** — SSE proxy with sliding-window detection, post-audit deep detection, and recall signals (SSE/webhook)
- **Plugin ecosystem** — in-process detectors via Python entry points, gRPC sidecar detectors in any language, official `z-llm-safety-gateway-sdk`, plugin CLI (`zlg`)
- **Security** — API-key auth, rate limiting, TLS termination, request-size limits, circuit breakers, per-detector timeouts, fail-open/fail-closed strategies
- **Observability** — Prometheus metrics, OpenTelemetry tracing, JSONL audit logging
- **Production-oriented** — Docker image, production Compose config (multi-replica, health checks, sidecar), 1000+ req/s single-instance throughput

## Quality & Performance

| Check | Result |
|-------|--------|
| Tests | **802 passed** (1 environment-skipped) |
| Coverage | **92%** |
| Lint / Type check | ruff clean · mypy clean |
| Detector accuracy | 4 rule-based detectors ≥ 90% on fixed sample sets |
| Latency (rule-based pipeline) | **P50 0.2ms / P95 0.4ms / P99 0.4ms** |
| Throughput (single instance) | **~6,600 req/s** |

Benchmarks target DESIGN §14 and are advisory (not CI-enforced).

## Quick Start

```bash
git clone https://github.com/zergcq-cell/z-llm-safety-gateway.git
cd z-llm-safety-gateway
pip install -e .

export OPENAI_API_KEY=sk-...
z-safety-gateway --config config/gateway.yaml
```

Or with Docker:

```bash
docker compose up -d
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [Configuration](docs/configuration.md)
- [API Specification](docs/api-spec.md)
- [Deployment](docs/deployment.md)
- [Plugin Development](docs/plugin-development.md)
- [gRPC Integration](docs/grpc-integration.md)

## What's Next

- **v0.2.0** — additional detectors (jailbreak, hallucination), mTLS for sidecars, provider failover, Redis-backed rate limiting, K8s Helm chart
- **v0.3.0 / v0.4.0** — Anthropic/Gemini providers, RBAC, multi-tenancy, agent execution rails, observability UI, plugin marketplace
- **v1.0.0** — general availability (stable public API)

See [DESIGN.md](DESIGN.md) for the full roadmap.

## Feedback

This is a test release — we want your feedback. Please open an [issue](https://github.com/zergcq-cell/z-llm-safety-gateway/issues/new/choose) for bugs, feature requests, or design feedback.

## License

[Apache License 2.0](LICENSE)
