"""Pydantic v2 configuration models for the z LLM Safety Gateway.

v0.2.0 refactors the detector configuration system:
- ``PipelineConfig.detectors`` changes from ``list[dict]`` to ``DetectorsConfig``
  with bidirectional ``input`` / ``output`` grouping.
- ``DetectorConfig`` gains ``priority``, ``on_error``, ``circuit_breaker``,
  ``config`` (nested block), and ``timeout`` fields.  Thresholds
  (``block_threshold`` / ``flag_threshold``) move into the nested ``config``
  dict.
- ``PipelineConfig`` gains ``execution_mode``, ``short_circuit_on``,
  ``sync_timeout``, and ``flag_escalation`` fields.
- ``GatewayConfig`` gains a top-level ``model_cache`` section.

Backward compatibility with v0.1.0 configs is preserved: a flat
``detectors: list[dict]`` is auto-converted to ``DetectorsConfig`` and
top-level ``block_threshold`` / ``flag_threshold`` keys are moved into the
nested ``config`` block.
"""

from __future__ import annotations

import warnings
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ServerConfig(BaseModel):
    """HTTP server configuration.

    v0.4.0 additions:
    - ``workers``: number of uvicorn worker processes (default 1).
    - ``stop_timeout``: graceful shutdown timeout (default '30s').
    """

    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    stop_timeout: str = "30s"


class ApiKeyConfig(BaseModel):
    """A single API key credential for gateway authentication."""

    key: str
    name: str = ""


class AuthConfig(BaseModel):
    """API Key bearer token authentication configuration (v0.4.0).

    Defaults to disabled. When enabled, requests without a valid Bearer token
    (matching one of ``api_keys``) are rejected with 401.
    """

    enabled: bool = False
    api_keys: list[ApiKeyConfig] = Field(default_factory=list)


class TLSConfig(BaseModel):
    """Native TLS termination configuration (v0.4.0).

    Defaults to disabled. When enabled, uvicorn is started with the given
    cert/key files for HTTPS termination.
    """

    enabled: bool = False
    cert_file: str = ""
    key_file: str = ""


class RateLimitConfig(BaseModel):
    """Token bucket rate limiting configuration (v0.4.0).

    - ``rate``: tokens replenished per second.
    - ``burst``: bucket capacity (allows bursts).
    - ``per``: bucket dimension ("api_key" or "ip").
    - ``storage``: "memory" (MVP); Redis deferred to v1.1+.
    """

    enabled: bool = False
    strategy: str = "token_bucket"
    rate: int = 100
    burst: int = 200
    per: str = "api_key"  # "api_key" | "ip"
    storage: str = "memory"  # "memory" (MVP) | "redis" (v1.1+)

    @field_validator("strategy")
    @classmethod
    def _validate_strategy(cls, v: str) -> str:
        if v != "token_bucket":
            raise ValueError(
                f"rate_limit.strategy must be 'token_bucket', got '{v}'"
            )
        return v

    @field_validator("per")
    @classmethod
    def _validate_per(cls, v: str) -> str:
        if v not in ("api_key", "ip"):
            raise ValueError(
                f"rate_limit.per must be 'api_key' or 'ip', got '{v}'"
            )
        return v

    @field_validator("storage")
    @classmethod
    def _validate_storage(cls, v: str) -> str:
        if v != "memory":
            raise ValueError(
                f"rate_limit.storage must be 'memory' in MVP, got '{v}'"
            )
        return v


class CORSConfig(BaseModel):
    """CORS configuration (v0.4.0)."""

    enabled: bool = False
    origins: list[str] = Field(default_factory=list)


class RequestIDConfig(BaseModel):
    """Request ID propagation configuration (v0.4.0).

    - ``header``: header name used for client-provided request IDs.
    - ``generate``: whether to accept client-provided IDs (True) or always
      generate a UUID (False).
    """

    header: str = "X-Request-ID"
    generate: bool = True


class TimeoutConfig(BaseModel):
    """Typed timeout configuration (v0.4.0).

    Durations are expressed as strings ('120s', '5s') in config and parsed
    to float seconds. ``upstream`` is the LLM provider timeout; ``detector``
    is the default per-detector timeout. Legacy integer values (e.g. ``120``)
    are accepted and treated as seconds for backward compatibility.
    """

    upstream: str = "120s"
    detector: str = "5s"

    @field_validator("upstream", "detector", mode="before")
    @classmethod
    def _coerce_int_to_duration(cls, v: Any) -> Any:
        """Coerce legacy integer seconds to a duration string."""
        if isinstance(v, int):
            return f"{v}s"
        return v

    @property
    def upstream_seconds(self) -> float:
        """Parse upstream duration string to float seconds."""
        return _parse_duration(self.upstream)

    @property
    def detector_seconds(self) -> float:
        """Parse detector duration string to float seconds."""
        return _parse_duration(self.detector)


def _parse_duration(value: str) -> float:
    """Parse a duration string like '120s' or '500ms' into float seconds.

    Args:
        value: Duration string; supports 's' (seconds) and 'ms' (milliseconds).

    Returns:
        Duration in seconds as a float.

    Raises:
        ValueError: If the string is not a valid duration.
    """
    value = value.strip()
    if value.endswith("ms"):
        return float(value[:-2]) / 1000.0
    if value.endswith("s"):
        return float(value[:-1])
    return float(value)


#: Gateway-internal fields inside a gRPC detector's ``config`` block.
#: These control the gateway's gRPC client and are NOT passed through to the
#: sidecar via InitializeRequest.config (DESIGN.md Section 7.5.1).
GRPC_GATEWAY_FIELDS = frozenset({"endpoint", "tls_enabled", "tls_ca_file"})


def passthrough_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return the detector ``config`` fields that are passed through to the plugin.

    Removes gateway-internal gRPC fields (``endpoint``, ``tls_enabled``,
    ``tls_ca_file``) so they are never forwarded to the sidecar
    (DESIGN.md Section 7.5.1 configuration passthrough).

    Args:
        config: The raw ``config`` dict from a gRPC detector's YAML.

    Returns:
        A new dict with only passthrough (vendor-facing) fields.
    """
    return {k: v for k, v in config.items() if k not in GRPC_GATEWAY_FIELDS}


class SecurityConfig(BaseModel):
    """Security-related configuration (v0.4.0).

    v0.4.0 refactors the flat ``timeout`` dict into typed sub-models:
    - ``auth``: API key authentication.
    - ``tls``: native TLS termination.
    - ``rate_limit``: token bucket rate limiting.
    - ``cors``: CORS support.
    - ``request_id``: request ID propagation policy.
    - ``max_request_size``: request body size limit.
    - ``timeout``: typed upstream/detector timeouts.
    """

    auth: AuthConfig = AuthConfig()
    tls: TLSConfig = TLSConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    cors: CORSConfig = CORSConfig()
    request_id: RequestIDConfig = RequestIDConfig()
    max_request_size: str = "10MB"
    timeout: TimeoutConfig = TimeoutConfig()


class ProviderConfig(BaseModel):
    """LLM provider configuration.

    Provider types:
    - openai: Official OpenAI API (requires api_key)
    - openai_compatible: Any OpenAI-compatible endpoint (api_key optional)
    - azure_openai: Azure OpenAI Service (requires api_key and api_version)
    """

    name: str
    type: str  # "openai" | "openai_compatible" | "azure_openai"
    base_url: str
    api_key: str = ""
    api_version: str = ""  # for azure_openai


class RoutingRule(BaseModel):
    """A single routing rule mapping a model pattern to a provider."""

    pattern: str
    provider: str


class RoutingConfig(BaseModel):
    """Routing configuration containing pattern-based rules."""

    rules: list[RoutingRule] = []


class FlagEscalationConfig(BaseModel):
    """Configuration for flag-to-block escalation rules.

    When ``enabled`` is True, the ``rule`` expression is parsed at config
    load time and evaluated at request time to determine whether accumulated
    ``flag`` results should be escalated to a ``block``.
    """

    enabled: bool = False
    rule: str = ""
    action: str = "block"


class CircuitBreakerConfig(BaseModel):
    """Configuration for a detector-level circuit breaker.

    Prevents cascading failures when a detector (especially external/gRPC)
    repeatedly errors.  The circuit transitions CLOSED -> OPEN after
    ``failure_threshold`` consecutive failures, and OPEN -> HALF_OPEN after
    ``recovery_timeout`` elapses.
    """

    enabled: bool = False
    failure_threshold: int = 5
    recovery_timeout: str = "30s"
    fallback_action: str = "fail_open"

    @field_validator("fallback_action")
    @classmethod
    def _validate_fallback_action(cls, v: str) -> str:
        if v not in ("fail_open", "fail_closed"):
            raise ValueError(
                f"fallback_action must be 'fail_open' or 'fail_closed', got '{v}'"
            )
        return v


class DetectorConfig(BaseModel):
    """Configuration for a single content safety detector.

    Thresholds (``block_threshold`` / ``flag_threshold``) live inside the
    nested ``config`` dict, not as top-level fields.  This allows different
    detector types to have different config schemas while sharing the same
    outer structure.

    Cross-field threshold validation (block > flag) is performed in
    ``validators._validate_detectors_v2()`` because it requires extracting
    values from the ``config`` dict.
    """

    name: str
    type: str = ""  # optional; "grpc" for gRPC sidecar detectors
    enabled: bool = True
    priority: int = 100
    on_error: str = "fail_open"  # "fail_open" | "fail_closed"
    circuit_breaker: CircuitBreakerConfig | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    timeout: str | None = None  # per-detector timeout override

    @field_validator("on_error")
    @classmethod
    def _validate_on_error(cls, v: str) -> str:
        if v not in ("fail_open", "fail_closed"):
            raise ValueError(
                f"on_error must be 'fail_open' or 'fail_closed', got '{v}'"
            )
        return v


class DetectorsConfig(BaseModel):
    """Bidirectional detector grouping.

    ``input`` detectors run on request content before provider forwarding.
    ``output`` detectors run on response content after provider response.
    """

    input: list[DetectorConfig] = []
    output: list[DetectorConfig] = []


class ModelCacheConfig(BaseModel):
    """Global ML model cache configuration.

    Provides defaults for all ML-based detectors.  Individual detectors can
    override via ``model_cache_dir`` and ``offline_mode`` in their own
    ``config`` section.
    """

    dir: str = "~/.cache/z_llm_safety_gateway/models/"
    offline_mode: bool = False


class StreamingRecallConfig(BaseModel):
    """Recall delivery configuration for streaming post-audit.

    ``method`` selects how a post-audit recall signal is delivered:
    - ``sse`` (default): emit a ``safety_recall`` SSE event on the active stream.
    - ``webhook``: POST the recall to ``webhook_url``.
    - ``both``: send the SSE event AND POST the webhook.
    """

    method: str = "sse"  # "sse" | "webhook" | "both"
    webhook_url: str = ""
    webhook_auth_header: str = ""

    @field_validator("method")
    @classmethod
    def _validate_method(cls, v: str) -> str:
        if v not in ("sse", "webhook", "both"):
            raise ValueError(
                f"recall.method must be 'sse', 'webhook', or 'both', got '{v}'"
            )
        return v


class StreamingConfig(BaseModel):
    """Streaming response safety detection configuration (v0.3.0).

    ``mode`` selects the streaming detection strategy:
    - ``sliding_window`` (default): detect on each character window as tokens
      arrive; block mid-stream if a risk is found.
    - ``buffer``: buffer the full response, run detection once, then replay the
      SSE chunks to the client (maximum safety, higher time-to-first-token).
    """

    mode: str = "sliding_window"  # "sliding_window" | "buffer"
    window_size: int = 200  # characters per window
    overlap: int = 50  # character overlap between consecutive windows
    send_flag_events: bool = False
    max_response_size: str = "1MB"  # byte-based accumulation limit
    on_max_size: str = "block"  # "block" | "truncate"
    post_audit: bool = True
    recall: StreamingRecallConfig = StreamingRecallConfig()

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("sliding_window", "buffer"):
            raise ValueError(
                f"streaming.mode must be 'sliding_window' or 'buffer', got '{v}'"
            )
        return v

    @field_validator("on_max_size")
    @classmethod
    def _validate_on_max_size(cls, v: str) -> str:
        if v not in ("block", "truncate"):
            raise ValueError(
                f"streaming.on_max_size must be 'block' or 'truncate', got '{v}'"
            )
        return v


class OutputRecallConfig(BaseModel):
    """Recall delivery configuration for non-streaming async output detection."""

    webhook_url: str = ""
    webhook_auth_header: str = ""


class OutputDetectionConfig(BaseModel):
    """Non-streaming output detection configuration (v0.3.0).

    ``mode`` selects how output detection runs for non-streaming responses:
    - ``sync`` (default): wait for output detection to complete before returning
      the response. May block (422), modify, or allow.
    - ``async``: return the response immediately, run detection in background,
      and send a webhook recall if a risk is found afterwards.
    """

    mode: str = "sync"  # "sync" | "async"
    sync_timeout: str = "5s"
    recall: OutputRecallConfig = OutputRecallConfig()

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("sync", "async"):
            raise ValueError(
                f"output_detection.mode must be 'sync' or 'async', got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def _validate_async_requires_webhook(
        self,
    ) -> OutputDetectionConfig:
        """Async mode requires a non-empty webhook_url for recall delivery."""
        if self.mode == "async" and not self.recall.webhook_url:
            raise ValueError(
                "output_detection.mode 'async' requires "
                "output_detection.recall.webhook_url to be configured"
            )
        return self


class PipelineConfig(BaseModel):
    """Pipeline configuration for content safety detection.

    v0.2.0 fields:
    - ``execution_mode``: MVP supports "parallel" only.
    - ``short_circuit_on``: "block" (default) or "block_and_modify".
    - ``sync_timeout``: pipeline-level timeout for output detection in sync mode.
    - ``flag_escalation``: optional flag-to-block escalation rule.
    - ``detectors``: ``DetectorsConfig`` with input/output grouping.

    v0.3.0 fields:
    - ``streaming``: ``StreamingConfig`` for SSE streaming safety detection.
    - ``output_detection``: ``OutputDetectionConfig`` for non-streaming output.

    Backward compat: accepts ``detectors`` as ``list[dict]`` (v0.1.0 format)
    and auto-converts to ``DetectorsConfig`` with all detectors in ``input``.
    """

    mode: str = "sync"
    execution_mode: str = "parallel"  # MVP only "parallel"
    short_circuit_on: str = "block"  # "block" | "block_and_modify"
    sync_timeout: str = "5s"
    flag_escalation: FlagEscalationConfig | None = None
    streaming: StreamingConfig = StreamingConfig()
    output_detection: OutputDetectionConfig = OutputDetectionConfig()
    detectors: DetectorsConfig | list[dict[str, Any]] = Field(
        default_factory=DetectorsConfig
    )

    @field_validator("short_circuit_on")
    @classmethod
    def _validate_short_circuit_on(cls, v: str) -> str:
        if v not in ("block", "block_and_modify"):
            raise ValueError(
                f"short_circuit_on must be 'block' or 'block_and_modify', got '{v}'"
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def _convert_legacy_detectors(cls, data: Any) -> Any:
        """Convert v0.1.0-style ``detectors: list[dict]`` to DetectorsConfig.

        Also moves top-level ``block_threshold`` / ``flag_threshold`` keys
        into the nested ``config`` dict for each detector, preserving
        backward compatibility with v0.1.0 config files.
        """
        if not isinstance(data, dict):
            return data

        detectors = data.get("detectors")
        if isinstance(detectors, list):
            # Old format: flat list -> {input: [...], output: []}
            converted = [_normalize_detector_dict(d) for d in detectors]
            data["detectors"] = {"input": converted, "output": []}
            warnings.warn(
                "pipeline.detectors as a flat list is deprecated; "
                "use {input: [...], output: [...]} format. "
                "All detectors have been assigned to 'input'.",
                UserWarning,
                stacklevel=2,
            )
        elif isinstance(detectors, dict):
            # New format: normalize detector dicts in input/output lists
            for key in ("input", "output"):
                if key in detectors and isinstance(detectors[key], list):
                    detectors[key] = [
                        _normalize_detector_dict(d) for d in detectors[key]
                    ]

        return data


class FileConfig(BaseModel):
    """JSONL audit log file output configuration (v0.3.0)."""

    enabled: bool = True
    path: str = "/var/log/safety-gateway"
    rotation: str = "daily"  # e.g. "daily", "midnight", "weekly"
    retention_days: int = 90


class AuditConfig(BaseModel):
    """Audit logging configuration.

    v0.3.0 additions:
    - ``store_content``: whether to store plaintext content (default false).
    - ``file``: JSONL file output config (enabled/path/rotation/retention_days).
    - ``stdout``: whether to emit structured JSON to stdout.
    """

    enabled: bool = False
    sanitize_logs: bool = True
    store_content: bool = False
    file: FileConfig = FileConfig()
    stdout: bool = True


class LoggingConfig(BaseModel):
    """Application logging configuration (v0.3.0)."""

    level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    format: str = "json"  # "json" | "text"

    @field_validator("level")
    @classmethod
    def _validate_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if v not in allowed:
            raise ValueError(
                f"logging.level must be one of {sorted(allowed)}, got '{v}'"
            )
        return v

    @field_validator("format")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        if v not in ("json", "text"):
            raise ValueError(
                f"logging.format must be 'json' or 'text', got '{v}'"
            )
        return v


class MetricsConfig(BaseModel):
    """Prometheus metrics configuration (v0.4.0)."""

    enabled: bool = False
    endpoint: str = "/metrics"


class TracingConfig(BaseModel):
    """OpenTelemetry tracing configuration (v0.4.0).

    Optional integration, disabled by default. ``exporter`` selects the
    trace exporter ("otlp"); ``sample_rate`` controls the sampling ratio.
    """

    enabled: bool = False
    exporter: str = "otlp"  # "otlp" | "jaeger" | "zipkin"
    endpoint: str = ""
    sample_rate: float = 0.1

    @field_validator("exporter")
    @classmethod
    def _validate_exporter(cls, v: str) -> str:
        if v not in ("otlp", "jaeger", "zipkin"):
            raise ValueError(
                f"tracing.exporter must be one of "
                f"'otlp', 'jaeger', 'zipkin', got '{v}'"
            )
        return v


class ObservabilityConfig(BaseModel):
    """Observability configuration (metrics and tracing).

    v0.4.0 refactors the flat boolean fields into nested sub-models:
    - ``metrics``: MetricsConfig (enabled/endpoint).
    - ``tracing``: TracingConfig (enabled/exporter/endpoint/sample_rate).
    """

    metrics: MetricsConfig = MetricsConfig()
    tracing: TracingConfig = TracingConfig()


class GatewayConfig(BaseModel):
    """Root configuration model for the z LLM Safety Gateway."""

    server: ServerConfig
    providers: list[ProviderConfig]
    routing: RoutingConfig
    pipeline: PipelineConfig = PipelineConfig()
    security: SecurityConfig = SecurityConfig()
    audit: AuditConfig = AuditConfig()
    logging: LoggingConfig = LoggingConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    model_cache: ModelCacheConfig = ModelCacheConfig()


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _normalize_detector_dict(d: Any) -> Any:
    """Move top-level threshold fields into the nested ``config`` dict.

    This preserves backward compatibility with v0.1.0 configs that specified
    ``block_threshold`` and ``flag_threshold`` as top-level DetectorConfig
    fields.  In v0.2.0 these fields live inside the ``config`` block.

    Args:
        d: A detector dict (or non-dict value, returned as-is).

    Returns:
        A new dict with thresholds moved into ``config``.
    """
    if not isinstance(d, dict):
        return d

    d = dict(d)  # shallow copy to avoid mutating caller's data
    config = dict(d.get("config", {}))

    # Move legacy top-level threshold fields into config dict
    for key in ("block_threshold", "flag_threshold"):
        if key in d:
            config[key] = d.pop(key)

    d["config"] = config
    return d
