"""Pydantic models for audit log entries (v0.3.0).

Each request generates one audit entry per direction (input / output), both
linked by the same ``request_id``.  See DESIGN.md Section 12.1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

from z_llm_safety_gateway.audit.streaming_evidence import StreamingEvidenceSummary
from z_llm_safety_gateway.flow.evidence import FlowEvidence, NodeEvidence
from z_llm_safety_gateway.tenancy.observation import TenantObservationContext


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
    policy_id: str = "legacy"
    detector_name: str
    direction: Literal["input", "output"]
    detector_type: str
    old_state: str
    new_state: str
    required: bool
    on_error: Literal["fail_open", "fail_closed"]
    reason_code: str = ""
    tenant_context: TenantObservationContext | None = Field(default=None, exclude=True)

    def to_json_line(self) -> dict[str, Any]:
        """Serialize the lifecycle event for the existing JSONL sinks."""
        data = self.model_dump()
        if self.tenant_context is not None:
            data["tenant_context"] = _tenant_context_json(self.tenant_context)
        return data


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
    # Additive v0.2.0 Flow evidence fields. Existing consumers may ignore them.
    flow_id: str | None = None
    flow_version: str | None = None
    flow_execution_id: str | None = None
    flow_status: str | None = None
    node_evidence: list[NodeEvidence] = Field(default_factory=list)
    evidence_persisted: bool = True
    streaming_evidence: StreamingEvidenceSummary | None = None
    tenant_context: TenantObservationContext | None = Field(default=None, exclude=True)
    # Content (only serialized when store_content=True)
    content: str | None = None
    _attached_flow_evidence: FlowEvidence | None = PrivateAttr(default=None)

    def with_flow_evidence(self, evidence: FlowEvidence) -> AuditEntry:
        """Attach a deterministic, payload-free Flow evidence snapshot in place."""
        self._attached_flow_evidence = evidence
        self.flow_id = evidence.flow_id
        self.flow_version = evidence.flow_version
        self.flow_execution_id = evidence.execution_id
        self.flow_status = evidence.status.value
        self.node_evidence = list(evidence.nodes)
        self.evidence_persisted = evidence.evidence_persisted
        return self

    @property
    def attached_flow_evidence(self) -> FlowEvidence | None:
        """Return the source evidence without adding it to the audit schema."""
        return self._attached_flow_evidence

    def to_json_line(self) -> dict[str, Any]:
        """Serialize the entry to a dict for JSON-line output (excluding content)."""
        data = self.model_dump(mode="json", exclude={"content"})
        if self.content is not None:
            data["content"] = self.content
        if self.tenant_context is not None:
            data["tenant_context"] = _tenant_context_json(self.tenant_context)
        return data


def _tenant_context_json(context: TenantObservationContext) -> dict[str, Any]:
    """Serialize the small, trusted observation projection explicitly."""
    return {
        "contract_version": context.contract_version,
        "scope": context.scope.value,
        "tenant_id": context.tenant_id,
        "policy_id": context.policy_id,
    }
