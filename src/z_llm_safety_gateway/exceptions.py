"""Custom exception classes and OpenAI-compatible error models.

This module provides:
- ConfigError / ConfigValidationError: configuration-related exceptions.
- OpenAIErrorDetail / OpenAIErrorBody: Pydantic models that serialize to the
  OpenAI API error format ({"error": {"message": ..., "type": ..., ...}}).
"""

from __future__ import annotations

from pydantic import BaseModel


class ConfigError(Exception):
    """Base exception for all configuration-related errors."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails (Pydantic or cross-field)."""


class OpenAIErrorDetail(BaseModel):
    """A single error detail in the OpenAI-compatible error format.

    Attributes:
        message: Human-readable error message.
        type: Error type category (e.g. "invalid_request_error",
            "provider_error", "internal_error").
        param: The parameter that caused the error, if applicable.
        code: Machine-readable error code (e.g. "model_not_found",
            "config_error").
    """

    message: str
    type: str = "internal_error"
    param: str | None = None
    code: str | None = None


class OpenAIErrorBody(BaseModel):
    """The top-level OpenAI-compatible error response body.

    Serializes to: {"error": {"message": ..., "type": ..., "param": ..., "code": ...}}
    """

    error: OpenAIErrorDetail
