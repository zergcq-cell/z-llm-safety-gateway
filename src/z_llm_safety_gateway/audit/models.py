"""Pydantic models for audit log entries (v0.3.0).

Each request generates one audit entry per direction (input / output), both
linked by the same ``request_id``.  See DESIGN.md Section 12.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class DetectorAuditRecord(BaseModel):
    """Audit record for a single detector execution."""

    name: str
    action: Literal["allow", "block", "flag", "modify"]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    duration_ms: float = 0.0
    error: str | None = None
    # Whether a modify action was actually applied to the request/response.
    # None = not applicable (non-modify actions); True = modify applied;
    # False = modify could not be applied (e.g. streaming post-audit downgrade).
    applied: bool | None = None


class DetectorAvailabilityRecord(BaseModel):
    """Stable request-time snapshot of an unavailable detector."""

    name: str
    direction: Literal["input", "output"]
    state: Literal["unavailable", "unhealthy"]
    required: bool
    on_error: Literal["fail_open", "fail_closed"]
    reason_code: str = ""


class DetectorLifecycleEvent(BaseModel):
    """Audit event emitted only when a configured detector changes state."""

    event_type: Literal["detector_lifecycle"] = "detector_lifecycle"
    timestamp: str = Field(default_factory=_utcnow)
    detector_name: str
    direction: Literal["input", "output"]
    detector_type: str
    old_state: str
    new_state: str
    required: bool
    on_error: Literal["fail_open", "fail_closed"]
    reason_code: str = ""

    def to_json_line(self) -> dict[str, Any]:
        """Serialize the lifecycle event for the existing JSONL sinks."""
        return self.model_dump()


class AuditEntry(BaseModel):
    """A single JSONL audit log entry for one direction of a request.

    Fields match DESIGN.md Section 12.1.  ``content`` is only serialized when
    ``store_content`` is enabled (default: content_hash only).
    """

    request_id: str
    timestamp: str = Field(default_factory=_utcnow)
    direction: Literal["input", "output"]
    user_id: str | None = None
    model: str | None = None
    provider: str | None = None
    content_hash: str | None = None
    content_length: int = 0
    language: str | None = None
    detectors: list[DetectorAuditRecord] = Field(default_factory=list)
    final_action: str = "allow"
    final_risk_level: str = "low"
    pipeline_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    streaming: bool = False
    # Streaming-specific fields (present only when streaming=True)
    window_count: int | None = None
    post_audit: dict[str, Any] | None = None
    post_audit_truncated: bool | None = None
    recalled: bool | None = None
    recall_method: str | None = None
    # Non-streaming async output detection
    async_detection: str | None = None  # "pending" | "completed"
    safety_degraded: bool = False
    detector_availability: list[DetectorAvailabilityRecord] = Field(default_factory=list)
    # Content (only serialized when store_content=True)
    content: str | None = None

    def to_json_line(self) -> dict[str, Any]:
        """Serialize the entry to a dict for JSON-line output (excluding content)."""
        data = self.model_dump(exclude={"content"})
        if self.content is not None:
            data["content"] = self.content
        return data
