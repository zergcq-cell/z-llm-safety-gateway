"""Audit logger — JSONL file + stdout structured output (v0.3.0).

Implements DESIGN.md Section 12.3 log output channels:
- JSONL file with daily rotation (``logging.handlers.TimedRotatingFileHandler``).
- stdout structured JSON for external collectors (Fluentd/Vector/Filebeat).

Content policy (Section 12.2): ``content_hash`` (SHA-256) is always stored;
``store_content`` controls whether plaintext content is also stored.
``sanitize_logs`` (default true) redacts secrets from stored content.
"""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
from pathlib import Path

from z_llm_safety_gateway.audit.models import AuditEntry
from z_llm_safety_gateway.audit.sanitizer import sanitize_content

logger = logging.getLogger("z_llm_safety_gateway.audit")


def compute_content_hash(content: str) -> str:
    """Return the SHA-256 hash of *content* prefixed with 'sha256:'."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class AuditLogger:
    """Writes audit entries to a JSONL file and/or stdout.

    Args:
        store_content: Whether to store plaintext content (default False).
        sanitize_logs: Whether to redact secrets from stored content.
        file_enabled: Whether to write to the JSONL file (default True).
        log_dir: Directory for the JSONL audit file.
        stdout_enabled: Whether to emit structured JSON to stdout (default True).
        enabled: Master switch; when False, no audit entries are written.
    """

    def __init__(
        self,
        store_content: bool = False,
        sanitize_logs: bool = True,
        file_enabled: bool = True,
        log_dir: str = "/var/log/safety-gateway",
        stdout_enabled: bool = True,
        enabled: bool = True,
        rotation: str = "daily",
        retention_days: int = 90,
    ) -> None:
        self._store_content = store_content
        self._sanitize_logs = sanitize_logs
        self._file_enabled = file_enabled
        self._stdout_enabled = stdout_enabled
        self._enabled = enabled
        self._rotation = rotation
        self._retention_days = retention_days

        self._file_handler: logging.Handler | None = None
        if file_enabled:
            self._file_handler = self._build_file_handler(log_dir, rotation)

    def _build_file_handler(
        self, log_dir: str, rotation: str
    ) -> logging.Handler | None:
        """Build a daily-rotating file handler for the JSONL audit log."""
        directory = Path(log_dir)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Directory creation failure — disable file output; audit continues
            # via stdout only. Failures are non-fatal per design.
            return None

        when = "midnight" if rotation == "daily" else rotation
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(directory / "audit.log"),
            when=when,
            backupCount=self._retention_days,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler

    def record(self, entry: AuditEntry) -> None:
        """Write an audit entry to the configured output channels.

        If ``store_content`` is disabled, content is dropped (hash only).
        If ``sanitize_logs`` is enabled, stored content is redacted.
        Failures are logged as warnings and never raise.
        """
        if not self._enabled:
            return

        data = entry.to_json_line()
        if entry.content is not None:
            if not self._store_content:
                data.pop("content", None)
            else:
                data["content"] = sanitize_content(entry.content, self._sanitize_logs)

        line = json.dumps(data, ensure_ascii=False)

        try:
            if self._file_handler is not None:
                self._file_handler.emit(
                    logging.LogRecord(
                        name="z_llm_safety_gateway.audit",
                        level=logging.INFO,
                        pathname="",
                        lineno=0,
                        msg=line,
                        args=(),
                        exc_info=None,
                    )
                )
        except Exception:  # pragma: no cover - defensive
            logger.warning("audit_file_write_failed", exc_info=True)

        if self._stdout_enabled:
            try:
                print(line)
            except Exception:  # pragma: no cover - defensive
                logger.warning("audit_stdout_write_failed", exc_info=True)

    def flush(self) -> None:
        """Flush the file handler (if any)."""
        if self._file_handler is not None:
            try:
                self._file_handler.flush()
            except Exception:  # pragma: no cover - defensive
                logger.warning("audit_flush_failed", exc_info=True)

    def close(self) -> None:
        """Close the file handler."""
        if self._file_handler is not None:
            self._file_handler.close()
