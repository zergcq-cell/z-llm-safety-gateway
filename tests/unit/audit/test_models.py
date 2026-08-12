"""Unit tests for audit log entry models.

Covers TC-AUD-001 through TC-AUD-005 (audit-logger spec).
"""

from __future__ import annotations

from z_llm_safety_gateway.audit.models import AuditEntry, DetectorAuditRecord


def _sample_detectors() -> list[DetectorAuditRecord]:
    return [
        DetectorAuditRecord(
            name="prompt_injection",
            action="block",
            confidence=0.92,
            risk_level="critical",
            duration_ms=15.0,
            error=None,
        )
    ]


# --------------------------------------------------------------------------- #
# TC-AUD-001: direction + request_id linking
# --------------------------------------------------------------------------- #
def test_audit_entry_direction_and_request_id():
    """TC-AUD-001: entry has direction and request_id for linking."""
    entry = AuditEntry(
        request_id="req_abc123",
        direction="input",
        model="gpt-4",
        provider="openai",
        content_hash="sha256:a1b2c3d4",
        content_length=1250,
        language="en",
        detectors=_sample_detectors(),
        final_action="block",
        final_risk_level="critical",
        pipeline_duration_ms=23.0,
        total_duration_ms=28.0,
        streaming=False,
    )
    assert entry.direction == "input"
    assert entry.request_id == "req_abc123"


# --------------------------------------------------------------------------- #
# TC-AUD-002: full field set
# --------------------------------------------------------------------------- #
def test_audit_entry_full_fields():
    """TC-AUD-002: entry includes all standard audit fields."""
    entry = AuditEntry(
        request_id="req_1",
        direction="output",
        user_id="user_001",
        model="gpt-4",
        provider="openai",
        content_hash="sha256:e5f6g7h8",
        content_length=850,
        language="en",
        detectors=_sample_detectors(),
        final_action="allow",
        final_risk_level="low",
        pipeline_duration_ms=38.0,
        total_duration_ms=42.0,
        streaming=False,
    )
    data = entry.model_dump()
    for field in (
        "request_id",
        "timestamp",
        "direction",
        "user_id",
        "model",
        "provider",
        "content_hash",
        "content_length",
        "language",
        "detectors",
        "final_action",
        "final_risk_level",
        "pipeline_duration_ms",
        "total_duration_ms",
        "streaming",
    ):
        assert field in data


# --------------------------------------------------------------------------- #
# TC-AUD-003: detectors array fields
# --------------------------------------------------------------------------- #
def test_detector_record_fields():
    """TC-AUD-003: detector record has name/action/confidence/risk_level/duration/error."""
    record = DetectorAuditRecord(
        name="toxicity",
        action="block",
        confidence=0.91,
        risk_level="high",
        duration_ms=35.0,
        error=None,
    )
    data = record.model_dump()
    for field in ("name", "action", "confidence", "risk_level", "duration_ms", "error"):
        assert field in data
    assert data["error"] is None


# --------------------------------------------------------------------------- #
# TC-AUD-004: streaming-specific fields
# --------------------------------------------------------------------------- #
def test_audit_entry_streaming_fields():
    """TC-AUD-004: streaming entry includes window_count/post_audit/recalled."""
    entry = AuditEntry(
        request_id="req_2",
        direction="output",
        model="gpt-4",
        provider="openai",
        content_hash="sha256:abc",
        content_length=2000,
        language="en",
        detectors=_sample_detectors(),
        final_action="block",
        final_risk_level="critical",
        pipeline_duration_ms=50.0,
        total_duration_ms=55.0,
        streaming=True,
        window_count=12,
        post_audit={
            "executed": True,
            "result": "block",
            "category": "toxicity",
            "risk_level": "critical",
        },
        post_audit_truncated=False,
        recalled=True,
        recall_method="sse",
    )
    data = entry.model_dump()
    assert data["streaming"] is True
    assert data["window_count"] == 12
    assert data["post_audit"]["executed"] is True
    assert data["recalled"] is True
    assert data["recall_method"] == "sse"


# --------------------------------------------------------------------------- #
# TC-AUD-005: content_hash always stored
# --------------------------------------------------------------------------- #
def test_audit_entry_content_hash_present():
    """TC-AUD-005: content_hash is always present."""
    entry = AuditEntry(
        request_id="req_3",
        direction="input",
        model="gpt-4",
        provider="openai",
        content_hash="sha256:xyz",
        content_length=10,
        language="en",
        detectors=[],
        final_action="allow",
        final_risk_level="low",
        pipeline_duration_ms=1.0,
        total_duration_ms=2.0,
        streaming=False,
    )
    assert entry.content_hash.startswith("sha256:")
