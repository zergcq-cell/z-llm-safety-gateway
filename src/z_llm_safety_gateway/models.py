"""Pydantic models for content extraction, modification, and detection."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExtractedContent(BaseModel):
    """Extracted text content from a chat message."""

    message_index: int
    role: str
    text: str


class Modification(BaseModel):
    """A content modification to apply to a message."""

    detector_name: str
    modified_content: str
    priority: int
    message_index: int | None = None


class DetectionResult(BaseModel):
    """Result returned by a detector after analyzing content.

    Fields detector_name, category, action, confidence, risk_level, and message
    are set by the detector. duration_ms and error are filled by the gateway.
    """

    detector_name: str
    category: str
    action: Literal["allow", "block", "flag", "modify"]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    modified_content: str | None = None
    duration_ms: float = 0.0
    error: str | None = None


class DetectionContext(BaseModel):
    """Context information passed to a detector for each detection call."""

    direction: Literal["input", "output"]
    request_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None
    message_index: int | None = None
