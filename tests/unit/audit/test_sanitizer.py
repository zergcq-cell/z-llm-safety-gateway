"""Unit tests for audit log sanitizer.

Covers TC-AUD-010 and TC-AUD-011 (audit-logger spec).
"""

from __future__ import annotations

from z_llm_safety_gateway.audit.sanitizer import redact_secrets, sanitize_content


# --------------------------------------------------------------------------- #
# TC-AUD-010: sanitize_logs=true redacts sensitive info
# --------------------------------------------------------------------------- #
def test_sanitize_content_redacts_api_key():
    """TC-AUD-010: API key patterns are redacted when sanitizing."""
    content = "My api key is sk-1234567890abcdef1234567890abcdef and auth Bearer tok_abcdef123"
    result = sanitize_content(content, enabled=True)
    assert "sk-1234567890abcdef1234567890abcdef" not in result
    assert "tok_abcdef123" not in result


def test_sanitize_content_redacts_authorization_header():
    """TC-AUD-010b: Authorization header values are redacted."""
    content = "Authorization: Bearer secret-token-value-123"
    result = sanitize_content(content, enabled=True)
    assert "secret-token-value-123" not in result


def test_redact_secrets_redacts_aws():
    """TC-AUD-010c: AWS secret keys are redacted."""
    content = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    result = redact_secrets(content)
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result


# --------------------------------------------------------------------------- #
# TC-AUD-011: sanitize_logs=false keeps content
# --------------------------------------------------------------------------- #
def test_sanitize_content_disabled_keeps_secrets():
    """TC-AUD-011: when disabled, content is unchanged."""
    content = "api key sk-1234567890abcdef1234567890abcdef"
    result = sanitize_content(content, enabled=False)
    assert result == content
