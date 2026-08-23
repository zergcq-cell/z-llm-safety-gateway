"""Bounded aggregation of per-window Flow evidence for streaming audit."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from z_llm_safety_gateway.flow.evidence import (
    DEFAULT_MAX_EVIDENCE_SIZE,
    FlowEvidence,
    bound_flow_evidence,
)

_TRIGGER_ACTIONS = frozenset({"block", "flag", "modify"})
_ACTION_PRECEDENCE = {"allow": 0, "flag": 1, "modify": 2, "block": 3}
_MAX_BUCKETS = 512
_MAX_TRIGGER_WINDOWS = 32


class StreamingEvidenceBucket(BaseModel):
    """One stable flow/node/action/reason aggregation bucket."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    flow_id: str
    flow_version: str
    node_id: str
    status: str
    reason_code: str
    action: str
    execution_count: int = Field(ge=1)
    degraded_count: int = Field(ge=0)
    trigger_window_indices: tuple[int, ...] = Field(
        default=(), max_length=_MAX_TRIGGER_WINDOWS
    )


class StreamingEvidenceSummary(BaseModel):
    """Final bounded streaming evidence attached to one audit record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "1.0"
    execution_count: int = Field(ge=0)
    buckets: tuple[StreamingEvidenceBucket, ...] = ()
    post_audit: FlowEvidence | None = None
    details_truncated: bool = False


@dataclass(slots=True)
class _MutableBucket:
    flow_id: str
    flow_version: str
    node_id: str
    status: str
    reason_code: str
    action: str
    execution_count: int = 0
    degraded_count: int = 0
    trigger_windows: tuple[int, ...] = ()


class StreamingEvidenceAccumulator:
    """Aggregate all window evidence without retaining raw per-window payloads."""

    def __init__(self, *, max_evidence_size: int = DEFAULT_MAX_EVIDENCE_SIZE) -> None:
        self._max_evidence_size = max_evidence_size
        self._execution_count = 0
        self._buckets: dict[tuple[str, ...], _MutableBucket] = {}
        self._post_audit: FlowEvidence | None = None
        self._details_truncated = False

    def record_window(self, evidence: FlowEvidence, *, window_index: int) -> None:
        """Count one completed window and aggregate each Node by stable dimensions."""
        self._execution_count += 1
        action = _flow_action(evidence)
        for node in evidence.nodes:
            key = (
                evidence.flow_id,
                evidence.flow_version,
                node.node_id,
                node.status.value,
                node.reason_code,
                action,
            )
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= _MAX_BUCKETS:
                    self._details_truncated = True
                    continue
                bucket = _MutableBucket(
                    flow_id=evidence.flow_id,
                    flow_version=evidence.flow_version,
                    node_id=node.node_id,
                    status=node.status.value,
                    reason_code=node.reason_code,
                    action=action,
                )
                self._buckets[key] = bucket
            bucket.execution_count += 1
            bucket.degraded_count += int(node.degraded)
            if (
                action in _TRIGGER_ACTIONS
                and len(bucket.trigger_windows) < _MAX_TRIGGER_WINDOWS
                and window_index not in bucket.trigger_windows
            ):
                bucket.trigger_windows = (*bucket.trigger_windows, window_index)

    def set_post_audit(self, evidence: FlowEvidence) -> None:
        """Retain post-audit as one independent full, already-bounded evidence object."""
        self._post_audit = evidence

    def summary(self) -> StreamingEvidenceSummary:
        """Return deterministic buckets under the total evidence budget."""
        buckets = tuple(
            StreamingEvidenceBucket(
                flow_id=bucket.flow_id,
                flow_version=bucket.flow_version,
                node_id=bucket.node_id,
                status=bucket.status,
                reason_code=bucket.reason_code,
                action=bucket.action,
                execution_count=bucket.execution_count,
                degraded_count=bucket.degraded_count,
                trigger_window_indices=bucket.trigger_windows,
            )
            for _, bucket in sorted(self._buckets.items())
        )
        summary = StreamingEvidenceSummary(
            execution_count=self._execution_count,
            buckets=buckets,
            post_audit=self._post_audit,
            details_truncated=self._details_truncated,
        )
        if len(summary.model_dump_json().encode()) <= self._max_evidence_size:
            return summary

        retained: list[StreamingEvidenceBucket] = []
        for bucket in sorted(
            buckets,
            key=lambda item: (
                -_ACTION_PRECEDENCE.get(item.action, 0),
                item.flow_id,
                item.node_id,
                item.reason_code,
            ),
        ):
            candidate = summary.model_copy(
                update={
                    "buckets": (*retained, bucket),
                    "details_truncated": True,
                }
            )
            if len(candidate.model_dump_json().encode()) > self._max_evidence_size:
                continue
            retained.append(bucket)
        bounded = summary.model_copy(
            update={"buckets": tuple(retained), "details_truncated": True}
        )
        if len(bounded.model_dump_json().encode()) <= self._max_evidence_size:
            return bounded

        if bounded.post_audit is not None:
            without_post_audit = bounded.model_copy(update={"post_audit": None})
            wrapper_size = len(without_post_audit.model_dump_json().encode()) - len(
                "null"
            )
            post_audit_budget = self._max_evidence_size - wrapper_size
            if post_audit_budget > 0:
                try:
                    compact_post_audit = bound_flow_evidence(
                        bounded.post_audit,
                        max_evidence_size=post_audit_budget,
                    )
                except ValueError:
                    compact_post_audit = None
                if compact_post_audit is not None:
                    with_compact_post_audit = bounded.model_copy(
                        update={"post_audit": compact_post_audit}
                    )
                    if (
                        len(with_compact_post_audit.model_dump_json().encode())
                        <= self._max_evidence_size
                    ):
                        return with_compact_post_audit

        # The post-audit evidence is also attached independently to the audit
        # entry. If its irreducible core cannot fit inside this secondary
        # streaming envelope, omit only the duplicate and mark truncation.
        return bounded.model_copy(update={"post_audit": None})


def _flow_action(evidence: FlowEvidence) -> str:
    actions = {
        signal.removeprefix("safety.")
        for signal in evidence.final_signals
        if signal.startswith("safety.")
    }
    return max(actions, key=lambda action: _ACTION_PRECEDENCE.get(action, -1), default="allow")
