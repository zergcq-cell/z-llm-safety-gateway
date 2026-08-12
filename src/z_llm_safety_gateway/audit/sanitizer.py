"""Log sanitization — redacts secrets from audit content (v0.3.0).

When ``sanitize_logs`` is enabled (default), sensitive patterns such as API
keys, AWS secret access keys, and Authorization headers are redacted before
content is written to the audit log.
"""

from __future__ import annotations

import re

# OpenAI-style API keys (sk-...).
_API_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")

# AWS secret access keys.
_AWS_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:aws_secret_access_key[=:]\s*|AKIA)[A-Za-z0-9/+=]{20,}\b"
)

# Bearer / API tokens (e.g. tok_..., Bearer <token>).
_TOKEN_PATTERN = re.compile(r"\btok_[A-Za-z0-9_-]{10,}\b")
_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=?")

# Authorization header values.
_AUTH_HEADER_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*)(\S+)")

_REDACTION = "[REDACTED]"


def redact_secrets(text: str) -> str:
    """Redact known secret patterns from *text*.

    Args:
        text: The content to sanitize.

    Returns:
        The content with secret patterns replaced by ``[REDACTED]``.
    """
    text = _API_KEY_PATTERN.sub(_REDACTION, text)
    text = _AWS_SECRET_PATTERN.sub(_REDACTION, text)
    text = _TOKEN_PATTERN.sub(_REDACTION, text)
    text = _BEARER_PATTERN.sub(_REDACTION, text)
    text = _AUTH_HEADER_PATTERN.sub(lambda m: m.group(1) + _REDACTION, text)
    return text


def sanitize_content(content: str, enabled: bool) -> str:
    """Sanitize *content* according to the *enabled* flag.

    Args:
        content: The content to sanitize.
        enabled: Whether sanitization is enabled. When False, content is
            returned unchanged.

    Returns:
        The sanitized (or original) content.
    """
    if not enabled:
        return content
    return redact_secrets(content)
