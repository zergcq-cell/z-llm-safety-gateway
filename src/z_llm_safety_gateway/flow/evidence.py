"""Bounded, deterministic, and payload-free Flow evidence models."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

from z_llm_safety_gateway.flow.policy import ResolvedNodePolicy

DEFAULT_MAX_EVIDENCE_SIZE = 256 * 1024
MAX_SIGNALS = 32

_REASON_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SIGNAL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX_256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _validate_reason_code(value: str) -> str:
    if not _REASON_PATTERN.fullmatch(value):
        raise ValueError("invalid_reason_code")
    return value


def _validate_bounded_identity(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 256:
        raise ValueError("invalid_evidence_identity")
    return normalized


ReasonCode = Annotated[str, AfterValidator(_validate_reason_code)]
EvidenceIdentity = Annotated[str, AfterValidator(_validate_bounded_identity)]


class _StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class NodeStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class FlowStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    STOPPED = "stopped"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class SafeEvidenceSummary(_StrictEvidenceModel):
    """Typed optional summary; raw messages and arbitrary plugin details are absent."""

    action: str | None = Field(default=None, max_length=32)
    risk_level: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=64)
    rule_ids: tuple[str, ...] = Field(default=(), max_length=16)
    match_count: int | None = Field(default=None, ge=0)
    confidence_bucket: str | None = Field(default=None, max_length=32)
    content_hash: str | None = None
    content_length: int | None = Field(default=None, ge=0)
    window_index: int | None = Field(default=None, ge=0)

    @field_validator("rule_ids")
    @classmethod
    def _validate_rule_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SIGNAL_PATTERN.fullmatch(value) for value in values):
            raise ValueError("invalid_rule_id")
        return values

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, value: str | None) -> str | None:
        if value is not None and not _HEX_256_PATTERN.fullmatch(value):
            raise ValueError("invalid_content_hash")
        return value


class NodeEvidence(_StrictEvidenceModel):
    """Core evidence emitted exactly once for every configured Node."""

    contract_version: Literal["1.0"]
    flow_id: EvidenceIdentity
    flow_version: EvidenceIdentity
    execution_id: EvidenceIdentity
    node_id: EvidenceIdentity
    definition_index: int = Field(ge=0)
    target_id: EvidenceIdentity
    target_contract_version: Literal["1.0"]
    target_implementation_version: EvidenceIdentity
    effective_policy: ResolvedNodePolicy
    status: NodeStatus
    degraded: bool
    reason_code: ReasonCode
    duration_ms: float = Field(ge=0)
    item_count: int = Field(ge=0)
    succeeded_items: int = Field(ge=0)
    failed_items: int = Field(ge=0)
    skipped_items: int = Field(ge=0)
    cancelled_items: int = Field(ge=0)
    signals: tuple[str, ...] = Field(default=(), max_length=MAX_SIGNALS)
    evidence_summary: SafeEvidenceSummary | None = None
    child_execution_id: EvidenceIdentity | None = None
    details_truncated: bool = False
    evidence_rejected_reason: ReasonCode | None = None

    @field_validator("signals")
    @classmethod
    def _validate_signals(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SIGNAL_PATTERN.fullmatch(value) for value in values):
            raise ValueError("invalid_evidence_signal")
        return values

    @field_serializer("effective_policy", when_used="json")
    def _serialize_effective_policy(
        self, policy: ResolvedNodePolicy
    ) -> dict[str, object]:
        """Serialize the complete policy without repetitive nested field names."""
        return {
            "timeout_seconds": policy.timeout.seconds,
            "timeout_action": policy.timeout.action,
            "failure_action": policy.failure.action,
            "required": policy.availability.required,
            "unavailable_action": policy.availability.on_unavailable,
            "circuit_open_action": policy.availability.on_circuit_open,
            "degradation_allowed": policy.degradation.allowed,
            "emit_evidence": policy.degradation.emit_evidence,
            "emit_metrics": policy.degradation.emit_metrics,
            "stop_signals": policy.stop.signals,
            "sources": (
                policy.sources.timeout.value,
                policy.sources.failure.value,
                policy.sources.availability.value,
                policy.sources.degradation.value,
                policy.sources.stop.value,
            ),
        }

    @model_validator(mode="after")
    def _validate_item_counts(self) -> NodeEvidence:
        if self.terminal_item_count != self.item_count:
            raise ValueError("evidence_item_count_mismatch")
        return self

    @property
    def terminal_item_count(self) -> int:
        return (
            self.succeeded_items
            + self.failed_items
            + self.skipped_items
            + self.cancelled_items
        )


class FlowEvidence(_StrictEvidenceModel):
    """Deterministically ordered evidence for one Flow execution."""

    contract_version: Literal["1.0"]
    execution_id: EvidenceIdentity
    parent_execution_id: EvidenceIdentity | None = None
    flow_id: EvidenceIdentity
    flow_version: EvidenceIdentity
    direction: Literal["input", "output"]
    stage: EvidenceIdentity
    status: FlowStatus
    reason_code: ReasonCode
    duration_ms: float = Field(ge=0)
    final_signals: tuple[str, ...] = Field(default=(), max_length=MAX_SIGNALS)
    nodes: tuple[NodeEvidence, ...] = ()
    evidence_persisted: bool = True
    details_truncated: bool = False

    @field_validator("final_signals")
    @classmethod
    def _validate_final_signals(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SIGNAL_PATTERN.fullmatch(value) for value in values):
            raise ValueError("invalid_evidence_signal")
        return values

    @field_validator("nodes")
    @classmethod
    def _sort_nodes(cls, values: tuple[NodeEvidence, ...]) -> tuple[NodeEvidence, ...]:
        return tuple(sorted(values, key=lambda node: (node.definition_index, node.node_id)))


def _compact_identity(value: str) -> str:
    """Return a stable, non-reversible identity when the evidence budget is tight."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
    return f"h:{digest}"


def _compact_stop_policy(policy: ResolvedNodePolicy) -> ResolvedNodePolicy:
    """Fingerprint a complete stop-signal set without changing other policy facts."""
    canonical_signals = json.dumps(
        policy.stop.signals,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical_signals.encode("utf-8")).hexdigest()[:24]
    compact_stop = policy.stop.model_copy(update={"signals": (f"h:{digest}",)})
    return policy.model_copy(update={"stop": compact_stop})


def bound_flow_evidence(
    evidence: FlowEvidence,
    *,
    max_evidence_size: int = DEFAULT_MAX_EVIDENCE_SIZE,
) -> FlowEvidence:
    """Enforce the budget on the complete serialized Flow evidence envelope.

    Optional summaries and signals are removed first. If unusually long plugin
    identities still exceed the budget, they are replaced by deterministic
    hashes. As a final tier, complete stop-signal sets become deterministic
    fingerprints while every Node terminal record and other policy fact remains.
    """
    if len(evidence.model_dump_json().encode()) <= max_evidence_size:
        return evidence

    bounded_nodes = tuple(
        node.model_copy(
            update={
                "signals": (),
                "evidence_summary": None,
                "details_truncated": True,
                "evidence_rejected_reason": "evidence_budget_exceeded",
            }
        )
        for node in evidence.nodes
    )
    bounded = evidence.model_copy(
        update={
            "final_signals": (),
            "nodes": bounded_nodes,
            "details_truncated": True,
        }
    )
    if len(bounded.model_dump_json().encode()) <= max_evidence_size:
        return bounded

    compact_nodes = tuple(
        node.model_copy(
            update={
                "flow_id": _compact_identity(node.flow_id),
                "flow_version": _compact_identity(node.flow_version),
                "execution_id": _compact_identity(node.execution_id),
                "node_id": _compact_identity(node.node_id),
                "target_id": _compact_identity(node.target_id),
                "target_implementation_version": _compact_identity(
                    node.target_implementation_version
                ),
                "child_execution_id": (
                    _compact_identity(node.child_execution_id)
                    if node.child_execution_id is not None
                    else None
                ),
                # The Flow-level truncation flag applies to the complete
                # envelope; one stable Node reason is enough to explain the
                # shared compaction without repeating it 256 times.
                "evidence_rejected_reason": (
                    "evidence_budget_exceeded" if index == 0 else None
                ),
            }
        )
        for index, node in enumerate(bounded.nodes)
    )
    compact = bounded.model_copy(
        update={
            "execution_id": _compact_identity(bounded.execution_id),
            "parent_execution_id": (
                _compact_identity(bounded.parent_execution_id)
                if bounded.parent_execution_id is not None
                else None
            ),
            "flow_id": _compact_identity(bounded.flow_id),
            "flow_version": _compact_identity(bounded.flow_version),
            "stage": _compact_identity(bounded.stage),
            "nodes": compact_nodes,
        }
    )
    if len(compact.model_dump_json().encode()) <= max_evidence_size:
        return compact

    policy_compact_nodes = tuple(
        node.model_copy(
            update={"effective_policy": _compact_stop_policy(node.effective_policy)}
        )
        for node in compact.nodes
    )
    policy_compact = compact.model_copy(update={"nodes": policy_compact_nodes})
    if len(policy_compact.model_dump_json().encode()) > max_evidence_size:
        raise ValueError("flow_evidence_budget_exceeded")
    return policy_compact


def _sanitize_signals(signals: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    valid = tuple(value for value in signals if _SIGNAL_PATTERN.fullmatch(value))
    truncated = len(valid) != len(signals) or len(valid) > MAX_SIGNALS
    return valid[:MAX_SIGNALS], truncated


def _sanitize_summary(
    optional_summary: SafeEvidenceSummary | Mapping[str, object] | None,
) -> tuple[SafeEvidenceSummary | None, bool]:
    if optional_summary is None:
        return None, False
    if isinstance(optional_summary, SafeEvidenceSummary):
        return optional_summary, False
    allowed_keys = set(SafeEvidenceSummary.model_fields)
    filtered = {key: value for key, value in optional_summary.items() if key in allowed_keys}
    rejected = len(filtered) != len(optional_summary)
    try:
        return SafeEvidenceSummary.model_validate(filtered), rejected
    except ValidationError:
        return None, True


def build_node_evidence(
    *,
    optional_summary: SafeEvidenceSummary | Mapping[str, object] | None = None,
    max_evidence_size: int = DEFAULT_MAX_EVIDENCE_SIZE,
    base_node: NodeEvidence | None = None,
    trusted_signals: bool = False,
    **core_fields: Any,
) -> NodeEvidence:
    """Build Node evidence while trimming optional data before immutable core fields."""
    raw_signals = tuple(core_fields.pop("signals", ()))
    if trusted_signals:
        signals, signals_truncated = raw_signals, False
    else:
        signals, signals_truncated = _sanitize_signals(raw_signals)
    summary, summary_rejected = _sanitize_summary(optional_summary)
    rejected_reason: str | None = None
    if summary_rejected:
        rejected_reason = "invalid_evidence_summary"
    elif signals_truncated:
        rejected_reason = "signal_limit_exceeded"

    evidence_fields = {
        **core_fields,
        "signals": signals,
        "evidence_summary": summary,
        "details_truncated": summary_rejected or signals_truncated,
        "evidence_rejected_reason": rejected_reason,
    }
    if base_node is not None:
        # Static contract and policy fields were validated when the runtime
        # built this template. Dynamic scheduler counts are reconciled here,
        # while capability-owned summaries and signals were sanitized above.
        node = base_node.model_copy(update=evidence_fields)
    else:
        node = NodeEvidence(**evidence_fields)
    # Every variable-length NodeEvidence field is schema-bounded, so a validated
    # node cannot approach the default 256 KiB budget. Serialize only when a
    # caller deliberately requests a tighter custom budget.
    if max_evidence_size >= DEFAULT_MAX_EVIDENCE_SIZE:
        return node
    if len(node.model_dump_json().encode()) <= max_evidence_size:
        return node

    node = node.model_copy(
        update={
            "signals": (),
            "evidence_summary": None,
            "details_truncated": True,
            "evidence_rejected_reason": "evidence_budget_exceeded",
        }
    )
    return node
