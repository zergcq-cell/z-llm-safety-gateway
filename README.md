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

The v0.1.1 packages are not yet published to PyPI. Install from the repository source. Python
3.10–3.12 is supported; Python 3.12 is recommended for a new environment.

```bash
# 1. Clone and create an isolated environment
git clone https://github.com/zergcq-cell/z-llm-safety-gateway.git
cd z-llm-safety-gateway
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .

# 2. Run the checked-in minimal configuration
export OPENAI_API_KEY=sk-replace-with-a-real-provider-key
z-safety-gateway --config config/gateway.yaml
```

In another terminal:

```bash
# 3. Verify process liveness and detector readiness
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

`/health` should return `{"status":"healthy"}` and `/ready` should return status `ready`.
Sending a chat request requires a valid provider key. See
[Getting Started](docs/getting-started.md) for the first request and detector checks.

Docker alternative:

```bash
OPENAI_API_KEY=sk-replace-with-a-real-provider-key docker compose up -d --build
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

## Community and Security

- Read [Contributing](CONTRIBUTING.md) before opening a pull request.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md) in all project spaces.
- Report vulnerabilities privately under the [Security Policy](SECURITY.md).
- Use the [issue chooser](https://github.com/zergcq-cell/z-llm-safety-gateway/issues/new/choose)
  for bug reports and feature requests that contain no sensitive security details.

## CLI Tools

```bash
zlg detectors list                  # list available detectors
zlg detectors test <name> --input "..."   # run a detector on sample input
zlg detectors check-connection <name>     # validate a gRPC sidecar
zlg-sdk new my-detector --type python     # scaffold a detector project
```

## Project Status

Current source version: **v0.1.1**, a public-test patch release. See
[DESIGN.md](DESIGN.md) for architecture and roadmap.

Supported Python versions: **3.10–3.12**; **3.12 is recommended** for releases and new
development environments.

**Versioning policy** (SemVer): `v0.0.x` = internal development · `v0.x.y` = public test releases · `v1.0.0` = general availability (when the API is stable and validated).

## License

[Apache License 2.0](LICENSE)
