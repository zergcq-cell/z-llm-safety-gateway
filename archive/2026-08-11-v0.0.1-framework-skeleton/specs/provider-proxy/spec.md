# provider-proxy - Behavioral Specification

> **Capability**: provider-proxy
> **Change**: 2026-08-11-v0.1.0-framework-skeleton
> **Created**: 2026-08-11T00:00:00+08:00
> **Confidence**: high

## Description

Transparent HTTP proxy that routes requests to LLM providers based on the `model` field using glob pattern matching, forwards the request to the matched provider, and returns the provider response to the client. Supports three provider types: `openai`, `openai_compatible`, and `azure_openai`. All provider errors are wrapped as OpenAI-compatible HTTP 502 `provider_error` responses.

---

## Requirements

### REQ-001: ModelRouter matches model field against routing rules using glob patterns, first match wins

**Confidence**: high

The ModelRouter evaluates the `model` field from the incoming request against routing rules defined in YAML configuration. Patterns are glob-style (e.g., `gpt-4*`, `llama*`). The first matching pattern in YAML declaration order determines the target provider.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-001 | high | Routing config in YAML order: `gpt-4*` -> openai, `gpt-3.5*` -> openai, `azure-*` -> azure_openai, `llama*` -> local_llama | Request with model `gpt-4-turbo` is routed | ModelRouter SHALL match `gpt-4*` (first matching pattern) and return the `openai` provider |
| SC-002 | high | Routing config with overlapping patterns `gpt-4*` -> openai and `gpt-*` -> local_llama in that YAML order | Request with model `gpt-4-turbo` is routed | ModelRouter SHALL match `gpt-4*` (first match in YAML order) and return the `openai` provider. The `gpt-*` pattern SHALL NOT be evaluated. |
| SC-003 | high | Routing config with rule `llama*` -> local_llama | Request with model `llama3-70b` is routed | ModelRouter SHALL match `llama*` and return the `local_llama` provider |

---

### REQ-002: If no routing rule matches, return HTTP 404 model_not_found error

**Confidence**: high

When no routing pattern matches the requested model, the gateway returns an OpenAI-compatible error response.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-004 | high | Routing config with rules `gpt-4*` -> openai and `llama*` -> local_llama | Request with model `claude-3-opus` has no matching pattern | Gateway SHALL return HTTP 404 with error type `invalid_request_error` and code `model_not_found`. The error message SHALL indicate no routing rule matches the requested model. |

---

### REQ-003: OpenAIProvider forwards request to OpenAI API with configured base_url and api_key

**Confidence**: high

The OpenAIProvider adapter forwards requests to the OpenAI API using the configured base URL and API key.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-005 | high | OpenAI provider configured with base_url `https://api.openai.com/v1` and api_key from environment variable | A chat completion request is forwarded to the OpenAI provider | OpenAIProvider SHALL forward the request to the configured base_url using httpx.AsyncClient. Authorization header SHALL contain `Bearer <api_key>`. Request body SHALL be passed through unmodified. Response SHALL be returned to the client. |

---

### REQ-004: OpenAICompatibleProvider forwards to any OpenAI-compatible endpoint

**Confidence**: high

The OpenAICompatibleProvider adapter forwards requests to OpenAI-compatible endpoints (Ollama, vLLM, LM Studio, etc.) without format conversion.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-006 | high | OpenAI-compatible provider configured with base_url `http://localhost:11434/v1` | A chat completion request is forwarded to the OpenAI-compatible provider | OpenAICompatibleProvider SHALL forward the request to the configured base_url. Request format SHALL be OpenAI-compatible with no format conversion. Response SHALL be returned to the client as-is. |

---

### REQ-005: AzureOpenAIProvider forwards to Azure OpenAI with api_version parameter

**Confidence**: high

The AzureOpenAIProvider adapter forwards requests to Azure OpenAI Service, including the configured `api_version` as a query parameter.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-007 | high | Azure OpenAI provider configured with base_url, api_key, and api_version `2024-06-01` | A chat completion request is forwarded to the Azure OpenAI provider | AzureOpenAIProvider SHALL forward the request to the configured base_url with the api_version as a query parameter. The `api-version` query parameter SHALL be set to the configured value. Authorization header SHALL contain `Bearer <api_key>`. |

---

### REQ-006: Provider timeout returns HTTP 502 provider_error

**Confidence**: high

When the provider does not respond within the configured `security.timeout.upstream`, the gateway aborts the request and returns an HTTP 502 error.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-008 | high | Provider configured with upstream timeout of 120 seconds | The provider does not respond within the configured timeout | Gateway SHALL return HTTP 502 with error type `provider_error` and code `provider_error`. The upstream request SHALL be aborted. The error.details SHALL contain the provider name and a timeout message. |

---

### REQ-007: Provider 4xx/5xx errors wrapped as HTTP 502 provider_error with original details

**Confidence**: high

Provider HTTP errors (4xx and 5xx) are wrapped into a unified HTTP 502 `provider_error` response. The original provider status code and error message are preserved in `error.details`.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-009 | high | A provider that returns HTTP 4xx (e.g., 400 Bad Request) or 5xx (e.g., 500 Internal Server Error) | The gateway receives the provider error response | Gateway SHALL wrap the error as HTTP 502 with error type `provider_error`. error.details SHALL contain the original provider status code, the original provider error message, and the provider name. If the provider returns a Retry-After header, it SHALL be forwarded to the client. |

---

### REQ-008: Provider network error returns HTTP 502 provider_error

**Confidence**: high

Network-level errors (connection refused, DNS resolution failure, etc.) when communicating with the provider are wrapped as HTTP 502 `provider_error` responses.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-010 | high | A provider with base_url pointing to an unreachable endpoint | The gateway attempts to forward a request and encounters a network error (connection refused, DNS failure) | Gateway SHALL return HTTP 502 with error type `provider_error`. error.details SHALL contain the provider name and a generic network error message. Detailed network error information SHALL be logged for debugging but not exposed to the client. |

---

### REQ-009: No retry in MVP - provider errors are returned directly to client

**Confidence**: high

The gateway does not retry failed provider requests. A single attempt is made; any error is returned directly to the client. Provider failover is not available in MVP.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-011 | high | A provider that returns an error (timeout, 4xx, 5xx, or network error) | The gateway receives the provider error | Gateway SHALL return the error response to the client without retrying the request. Only one attempt SHALL be made to the provider. Provider failover SHALL NOT be available in MVP. |

---

### REQ-010: Routing conflict detection - overlapping glob patterns produce startup warning

**Confidence**: high

During startup configuration validation, the gateway detects overlapping glob patterns in routing rules and logs a warning. This does not block startup.

| Scenario | Confidence | Given | When | Then |
|----------|------------|-------|------|------|
| SC-012 | high | A routing configuration with overlapping patterns `gpt-4*` -> openai and `gpt-*` -> local_llama | The gateway starts up and validates the routing configuration | Gateway SHALL log a warning about overlapping routing rules. The warning SHALL identify which patterns overlap and for which model names. The warning SHALL state which pattern will take precedence (first match). The gateway SHALL still start successfully (warning does not block startup). |
