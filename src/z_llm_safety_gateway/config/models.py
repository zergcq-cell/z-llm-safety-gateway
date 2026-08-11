"""Pydantic v2 configuration models for the z LLM Safety Gateway."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, model_validator


class ServerConfig(BaseModel):
    """HTTP server configuration."""

    host: str = "0.0.0.0"
    port: int = 8080


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


class PipelineConfig(BaseModel):
    """Pipeline configuration for content safety detection."""

    mode: str = "sync"
    detectors: list[dict[str, Any]] = []


class DetectorConfig(BaseModel):
    """Configuration for a single content safety detector.

    Cross-field validation ensures block_threshold is strictly greater than
    flag_threshold, so that blocking is always a stricter action than flagging.
    """

    name: str
    type: str
    enabled: bool = True
    block_threshold: float = 0.85
    flag_threshold: float = 0.50

    @model_validator(mode="after")
    def validate_thresholds(self) -> DetectorConfig:
        """Ensure block_threshold > flag_threshold (strictly)."""
        if self.block_threshold <= self.flag_threshold:
            raise ValueError(
                f"Detector '{self.name}': block_threshold ({self.block_threshold}) "
                f"must be strictly greater than flag_threshold ({self.flag_threshold})"
            )
        return self


class SecurityConfig(BaseModel):
    """Security-related configuration."""

    timeout: dict[str, int] = {"upstream": 120}


class AuditConfig(BaseModel):
    """Audit logging configuration."""

    enabled: bool = False
    sanitize_logs: bool = True


class ObservabilityConfig(BaseModel):
    """Observability configuration (metrics and tracing)."""

    metrics_enabled: bool = False
    tracing_enabled: bool = False


class GatewayConfig(BaseModel):
    """Root configuration model for the z LLM Safety Gateway."""

    server: ServerConfig
    providers: list[ProviderConfig]
    routing: RoutingConfig
    pipeline: PipelineConfig = PipelineConfig()
    security: SecurityConfig = SecurityConfig()
    audit: AuditConfig = AuditConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
