"""Custom exception classes and OpenAI-compatible error models.

This module provides:
- ConfigError / ConfigValidationError: configuration-related exceptions.
- SafetyBlockError: raised when the safety pipeline blocks a request or response.
- OpenAIErrorDetail / OpenAIErrorBody: Pydantic models that serialize to the
  OpenAI API error format ({"error": {"message": ..., "type": ..., ...}}).
- SafetyErrorDetail: OpenAI error detail with safety extension field.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ConfigError(Exception):
    """Base exception for all configuration-related errors."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails (Pydantic or cross-field)."""


class DetectorInitializationError(ConfigError):
    """Raised when a required safety detector cannot initialize."""

    def __init__(self, detector_name: str, direction: str) -> None:
        self.detector_name = detector_name
        self.direction = direction
        super().__init__(
            f"Required detector '{detector_name}' failed to initialize for {direction}"
        )


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


class SafetyBlockError(Exception):
    """Raised when the safety pipeline blocks a request or response.

    Attributes:
        detector_name: Name of the detector that triggered the block.
        category: Detection category (e.g. "prompt_injection", "pii").
        risk_level: Risk level of the blocked content ("low" through "critical").
        confidence: Confidence score [0.0, 1.0] from the blocking detector.
        message: Human-readable description of why the content was blocked.
        direction: Whether the block occurred on "input" or "output".
    """

    def __init__(
        self,
        detector_name: str,
        category: str,
        risk_level: str,
        confidence: float,
        message: str,
        direction: str,
    ) -> None:
        self.detector_name = detector_name
        self.category = category
        self.risk_level = risk_level
        self.confidence = confidence
        self.message = message
        self.direction = direction  # "input" or "output"
        super().__init__(message)


class SafetyUnavailableError(Exception):
    """Raised before Provider work when required safety capability is unavailable."""

    def __init__(self, affected_directions: list[str], detectors: list[str]) -> None:
        self.affected_directions = sorted(set(affected_directions))
        self.detectors = sorted(set(detectors))
        super().__init__("Safety detection is temporarily unavailable")


class SafetyErrorDetail(OpenAIErrorDetail):
    """OpenAI error detail with a safety extension field.

    The ``safety`` dict contains: detector_name, category, risk_level,
    confidence, message, and direction — providing full context about
    why the safety pipeline blocked the request or response.
    """

    safety: dict[str, Any] | None = None


class OpenAIErrorBody(BaseModel):
    """The top-level OpenAI-compatible error response body.

    Serializes to: {"error": {"message": ..., "type": ..., "param": ..., "code": ...}}
    """

    error: OpenAIErrorDetail
