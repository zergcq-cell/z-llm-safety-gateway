# z LLM Safety Gateway

Open-source, modular LLM content safety gateway that acts as a transparent proxy between applications and LLM providers, performing real-time content safety detection and filtering.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Transparent proxy** — OpenAI-compatible `/v1/chat/completions` endpoint, forwards to upstream providers (OpenAI, Azure, compatible endpoints)
- **Multi-layer safety pipeline** — prompt injection, PII redaction, toxicity, sensitive words, secret leak detection (parallel execution, configurable thresholds)
- **Streaming safety** — SSE proxy with sliding-window detection, post-audit deep detection, and recall signals (SSE/webhook)
- **Plugin ecosystem** — in-process plugins via Python entry points, gRPC sidecar detectors in any language, official Detector SDK (`z-llm-safety-gateway-sdk`)
- **Security & observability** — API key auth, rate limiting, TLS, request size limits, Prometheus metrics, OpenTelemetry tracing, JSONL audit logging
- **Enterprise ready** — circuit breakers, per-detector timeouts, fail-open/fail-closed strategies, graceful shutdown

## Quick Start

```bash
# 1. Install
pip install z-llm-safety-gateway

# 2. Configure (see docs/configuration.md for all options)
cat > config/gateway.yaml <<'YAML'
server:
  host: 0.0.0.0
  port: 8080
providers:
  - name: openai
    type: openai
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
routing:
  rules:
    - pattern: gpt-4*
      provider: openai
pipeline:
  detectors:
    input:
      - name: prompt_injection
        enabled: true
YAML

# 3. Run
z-safety-gateway --config config/gateway.yaml

# 4. Smoke test
curl http://localhost:8080/health
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"Hello"}]}'
```

Or with Docker:

```bash
docker compose up -d
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Install, minimal config, first request |
| [Configuration](docs/configuration.md) | All config blocks with examples |
| [API Specification](docs/api-spec.md) | Endpoints, request/response, error formats |
| [Deployment](docs/deployment.md) | Docker, production tips, sidecar integration |
| [Plugin Development](docs/plugin-development.md) | Build in-process or gRPC detectors |
| [gRPC Integration](docs/grpc-integration.md) | Sidecar contract, lifecycle, TLS, debugging |
| [Commercial Plugins](docs/commercial-plugin.md) | License, packaging, monetization |

## CLI Tools

```bash
zlg detectors list                  # list available detectors
zlg detectors test <name> --input "..."   # run a detector on sample input
zlg detectors check-connection <name>     # validate a gRPC sidecar
zlg-sdk new my-detector --type python     # scaffold a detector project
```

## Project Status

v1.0.0 — Production Ready. See [DESIGN.md](DESIGN.md) for architecture and roadmap.

## License

[Apache License 2.0](LICENSE)
