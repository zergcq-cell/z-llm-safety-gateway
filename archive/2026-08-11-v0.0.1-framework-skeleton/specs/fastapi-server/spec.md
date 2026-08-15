# fastapi-server - Behavioral Specification (Human View)

> **Change**: 2026-08-11-v0.1.0-framework-skeleton
> **Capability**: fastapi-server
> **Created**: 2026-08-11T00:00:00+08:00
> **Confidence**: high

## Description

FastAPI HTTP server that listens on a configured host:port and provides OpenAI-compatible API endpoints (`/v1/chat/completions`, `/v1/models`). Implements the app factory pattern, global error handling with OpenAI-compatible error format, and transparent request forwarding to upstream LLM providers.

---

## Requirements

### REQ-001: App Factory Pattern

**Description**: `create_app(config_path)` creates a FastAPI instance with loaded configuration.

**Confidence**: high

#### SC-001: create_app returns configured FastAPI instance

- **Given**: a valid YAML config file path containing server, providers, and routing sections
- **When**: `create_app(config_path)` is called
- **Then**: the function **SHALL** return a FastAPI application instance
- **And**:
  - the returned app **SHALL** have loaded the configuration from the given path
  - the returned app **SHALL** have registered all route handlers (`/v1/chat/completions`, `/v1/models`, `/health`, `/ready`, `/metrics`)
  - the returned app **SHALL** have registered RequestIDMiddleware
  - the returned app **SHALL** have registered global exception handlers for ProviderError and ConfigError
  - calling `create_app` with different config paths **SHALL** produce independent app instances

#### SC-002: create_app raises on missing config file

- **Given**: a config file that does not exist on disk
- **When**: `create_app(config_path)` is called
- **Then**: the function **SHALL** raise an exception that prevents the app from starting
- **And**:
  - the exception message **SHALL** include the config file path that was not found

---

### REQ-002: /v1/chat/completions Endpoint

**Description**: `/v1/chat/completions` endpoint accepts POST requests, parses the body, forwards to the matched provider, and returns the provider response.

**Confidence**: high

#### SC-003: Forward request to provider and return response

- **Given**: a running gateway instance with a configured provider and a routing rule matching model `gpt-4*`
- **When**: a POST request is sent to `/v1/chat/completions` with a JSON body containing model `gpt-4` and a messages array
- **Then**: the endpoint **SHALL** accept the request and return the provider response as-is to the client
- **And**:
  - the response status code **SHALL** match the provider response status code
  - the response body **SHALL** be the provider response body forwarded transparently
  - the response **SHALL** include the `X-Request-ID` header
  - the response **SHALL** include the `X-Safety-Action: allow` header

#### SC-004: Unmatched model returns 404 model_not_found

- **Given**: a running gateway instance with a routing rule matching model `gpt-4*`
- **When**: a POST request is sent to `/v1/chat/completions` with a model field that matches no routing rule
- **Then**: the endpoint **SHALL** return HTTP 404 with an OpenAI-compatible error of type `invalid_request_error` and code `model_not_found`
- **And**:
  - the error response **SHALL** include the `X-Request-ID` header
  - the error message **SHALL** indicate that no routing rule matches the requested model

#### SC-005: Invalid JSON body returns 400

- **Given**: a running gateway instance
- **When**: a POST request is sent to `/v1/chat/completions` with a body that is not valid JSON
- **Then**: the endpoint **SHALL** return HTTP 400 with an OpenAI-compatible error
- **And**:
  - the error response **SHALL** include the `X-Request-ID` header

---

### REQ-003: /v1/models Endpoint

**Description**: `/v1/models` endpoint forwards the request to the first configured provider and returns the model list as-is.

**Confidence**: high

#### SC-006: Forward to first provider and return model list

- **Given**: a running gateway instance with at least one configured provider
- **When**: a GET request is sent to `/v1/models`
- **Then**: the endpoint **SHALL** forward the request to the first configured provider and return the provider response as-is
- **And**:
  - the response status code **SHALL** match the provider response status code
  - the response body **SHALL** be the provider model list forwarded transparently
  - the response **SHALL** include the `X-Request-ID` header
  - no model aggregation across multiple providers **SHALL** be performed in Phase 1

---

### REQ-004: Server Starts and Listens on Configured Host:Port

**Description**: Server starts and listens on the configured host:port.

**Confidence**: high

#### SC-007: Server binds to configured address

- **Given**: a valid config file with `server.host` set to `127.0.0.1` and `server.port` set to `8080`
- **When**: the server is started using the created app instance
- **Then**: the server **SHALL** bind to and listen on `127.0.0.1:8080`
- **And**:
  - the server **SHALL** accept incoming HTTP connections on the configured port
  - the server configuration **SHALL** be loaded once at startup, not per request

#### SC-008: App factory importable without starting server

- **Given**: a valid config file with a custom host and port
- **When**: the server is started with uvicorn referencing the app factory
- **Then**: the server **SHALL** start successfully without import-time side effects
- **And**:
  - the app factory **SHALL** be importable without starting the server

---

### REQ-005: Global Error Handler for Provider Errors

**Description**: Global error handler wraps provider errors as OpenAI-compatible format with HTTP 502 `provider_error`.

**Confidence**: high

#### SC-009: Provider 5xx error wrapped as 502 provider_error

- **Given**: a running gateway instance with a configured provider that returns a 5xx error
- **When**: a request is forwarded to the provider and the provider returns an error response
- **Then**: the gateway **SHALL** return HTTP 502 with an OpenAI-compatible error body of type `provider_error`
- **And**:
  - the error body **SHALL** include a `details` field containing the provider name and original provider message
  - the error response **SHALL** include the `X-Request-ID` header

#### SC-010: Provider timeout wrapped as 502 provider_error

- **Given**: a running gateway instance with a configured provider that times out
- **When**: a request is forwarded to the provider and the upstream timeout is exceeded
- **Then**: the gateway **SHALL** return HTTP 502 with an OpenAI-compatible error body of type `provider_error`
- **And**:
  - the error message **SHALL** indicate a connection timeout
  - the gateway **SHALL** abort the upstream request

#### SC-011: Provider 4xx error wrapped as 502 provider_error

- **Given**: a running gateway instance with a configured provider that returns a 4xx error (e.g., 400, 401, 403)
- **When**: a request is forwarded to the provider and the provider returns a 4xx error
- **Then**: the gateway **SHALL** wrap the error and return HTTP 502 with an OpenAI-compatible error body of type `provider_error`
- **And**:
  - the error `details` field **SHALL** include the original provider status code
  - the error `details` field **SHALL** include the original provider message
  - the gateway **SHALL NOT** retry the request

---

### REQ-006: Global Error Handler for Config Errors

**Description**: Global error handler wraps config errors as HTTP 500 `internal_error`.

**Confidence**: high

#### SC-012: ConfigError wrapped as 500 internal_error

- **Given**: a running gateway instance that encounters a configuration error during request processing
- **When**: a `ConfigError` exception is raised within a route handler
- **Then**: the global exception handler **SHALL** return HTTP 500 with an OpenAI-compatible error body of type `internal_error`
- **And**:
  - the error code **SHALL** be `config_error`
  - the error response **SHALL** include the `X-Request-ID` header
  - the error message **SHALL** describe the configuration issue without exposing internal secrets

#### SC-013: Unhandled Exception wrapped as 500 internal_error

- **Given**: a running gateway instance that encounters an unexpected exception during request processing
- **When**: an unhandled `Exception` is raised within a route handler
- **Then**: the global exception handler **SHALL** return HTTP 500 with an OpenAI-compatible error body of type `internal_error`
- **And**:
  - the error response **SHALL** include the `X-Request-ID` header
  - the internal exception details **SHALL** be logged but **NOT** exposed in the response body

---

## Verification Checkpoints

| CP | Scenario | Description |
|----|----------|-------------|
| CP-1 | SC-001 | create_app returns FastAPI instance with registered routes |
| CP-2 | SC-002 | create_app raises on missing config file |
| CP-3 | SC-003 | POST /v1/chat/completions forwards and returns provider response |
| CP-4 | SC-004 | Unmatched model returns 404 model_not_found |
| CP-5 | SC-005 | Invalid JSON body returns 400 |
| CP-6 | SC-006 | GET /v1/models forwards to first provider |
| CP-7 | SC-007 | Server binds to configured host:port |
| CP-8 | SC-008 | App factory importable without starting server |
| CP-9 | SC-009 | Provider 5xx error wrapped as 502 provider_error |
| CP-10 | SC-010 | Provider timeout wrapped as 502 provider_error |
| CP-11 | SC-011 | Provider 4xx error wrapped as 502 provider_error |
| CP-12 | SC-012 | ConfigError wrapped as 500 internal_error |
| CP-13 | SC-013 | Unhandled Exception wrapped as 500 internal_error |
| CP-14 | -- | Full test suite pass |
| CP-15 | -- | Lint and type checks pass |
