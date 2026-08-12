"""Unit tests for AuditLogger.

Covers TC-AUD-006 through TC-AUD-009 and TC-AUD-012 through TC-AUD-013.
"""

from __future__ import annotations

import json

from z_llm_safety_gateway.audit.logger import AuditLogger
from z_llm_safety_gateway.audit.models import AuditEntry, DetectorAuditRecord


def _entry(request_id: str = "req_1", content: str | None = None) -> AuditEntry:
    return AuditEntry(
        request_id=request_id,
        direction="input",
        model="gpt-4",
        provider="openai",
        content_hash="sha256:abc",
        content_length=len(content) if content else 0,
        language="en",
        detectors=[
            DetectorAuditRecord(
                name="pii_redaction",
                action="flag",
                confidence=0.60,
                risk_level="medium",
                duration_ms=8.0,
                error=None,
            )
        ],
        final_action="flag",
        final_risk_level="medium",
        pipeline_duration_ms=23.0,
        total_duration_ms=28.0,
        streaming=False,
        content=content,
    )


# --------------------------------------------------------------------------- #
# TC-AUD-006: store_content=false stores only hash
# --------------------------------------------------------------------------- #
def test_store_content_false_no_plaintext(tmp_path):
    """TC-AUD-006: with store_content false, content is not written."""
    logger = AuditLogger(
        store_content=False,
        sanitize_logs=True,
        file_enabled=True,
        log_dir=str(tmp_path),
    )
    logger.record(_entry(content="secret text here"))
    logger.flush()
    lines = list(tmp_path.glob("*.log")) + list(tmp_path.glob("*.jsonl"))
    assert lines, "expected a log file to be written"
    data = json.loads(lines[0].read_text().strip().splitlines()[-1])
    assert "content" not in data or data.get("content") is None
    assert data["content_hash"].startswith("sha256:")


# --------------------------------------------------------------------------- #
# TC-AUD-007: store_content=true stores plaintext
# --------------------------------------------------------------------------- #
def test_store_content_true_stores_plaintext(tmp_path):
    """TC-AUD-007: with store_content true, content is written."""
    logger = AuditLogger(
        store_content=True,
        sanitize_logs=False,
        file_enabled=True,
        log_dir=str(tmp_path),
    )
    logger.record(_entry(content="visible plaintext"))
    logger.flush()
    lines = list(tmp_path.glob("*.log")) + list(tmp_path.glob("*.jsonl"))
    data = json.loads(lines[0].read_text().strip().splitlines()[-1])
    assert data["content"] == "visible plaintext"


# --------------------------------------------------------------------------- #
# TC-AUD-008: JSONL file writing (daily rotation via handler)
# --------------------------------------------------------------------------- #
def test_logger_writes_jsonl_file(tmp_path):
    """TC-AUD-008: audit entry is written as JSON line to file."""
    logger = AuditLogger(
        store_content=False,
        sanitize_logs=True,
        file_enabled=True,
        log_dir=str(tmp_path),
    )
    logger.record(_entry())
    logger.flush()
    files = list(tmp_path.iterdir())
    assert files, "audit file should be created"
    content = files[0].read_text().strip()
    parsed = json.loads(content.splitlines()[-1])
    assert parsed["request_id"] == "req_1"
    assert parsed["direction"] == "input"


# --------------------------------------------------------------------------- #
# TC-AUD-009: stdout structured output
# --------------------------------------------------------------------------- #
def test_logger_stdout_output(tmp_path, capsys):
    """TC-AUD-009: audit entry is emitted to stdout as JSON."""
    logger = AuditLogger(
        store_content=False,
        sanitize_logs=True,
        file_enabled=False,
        log_dir=str(tmp_path),
        stdout_enabled=True,
    )
    logger.record(_entry())
    logger.flush()
    captured = capsys.readouterr()
    assert captured.out.strip(), "expected stdout JSON output"
    parsed = json.loads(captured.out.strip().splitlines()[-1])
    assert parsed["final_action"] == "flag"


# --------------------------------------------------------------------------- #
# TC-AUD-012: async write failure only warns (does not raise)
# --------------------------------------------------------------------------- #
def test_logger_write_failure_does_not_raise(tmp_path):
    """TC-AUD-012: writing to an invalid path does not raise."""
    logger = AuditLogger(
        store_content=False,
        sanitize_logs=True,
        file_enabled=True,
        log_dir="/nonexistent/definitely/missing/dir",
    )
    # record + flush should not raise even though the dir does not exist
    logger.record(_entry())
    logger.flush()


# --------------------------------------------------------------------------- #
# TC-AUD-013: audit disabled writes nothing
# --------------------------------------------------------------------------- #
def test_logger_disabled_writes_nothing(tmp_path, capsys):
    """TC-AUD-013: when disabled, no audit record is written."""
    logger = AuditLogger(
        store_content=False,
        sanitize_logs=True,
        file_enabled=True,
        log_dir=str(tmp_path),
        enabled=False,
    )
    logger.record(_entry())
    logger.flush()
    captured = capsys.readouterr()
    assert captured.out.strip() == ""
