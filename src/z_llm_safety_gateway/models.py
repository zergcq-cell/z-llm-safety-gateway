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


def find_result_by_action(
    results: list[DetectionResult], actions: str | set[str]
) -> DetectionResult | None:
    """Find the first DetectionResult whose action matches.

    Unlike ``results[0]``, this returns the detector that actually triggered
    the given action, not just the first detector in the list (which may
    have returned ``allow``).

    Args:
        results: List of detection results to search.
        actions: A single action string (e.g. ``"block"``) or a set of
            action strings (e.g. ``{"flag", "modify"}``) to match.

    Returns:
        The first matching DetectionResult, or None if no match.
    """
    action_set = {actions} if isinstance(actions, str) else set(actions)
    return next((r for r in results if r.action in action_set), None)
