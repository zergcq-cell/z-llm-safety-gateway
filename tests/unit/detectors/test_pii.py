"""Tests for the PIIDetector: PII detection and redaction.

Covers STDD v0.2.0 Slice 3 requirements:
- REQ-001: Detect multiple PII types (email, phone, ssn, credit_card, ip_address)
- REQ-002: Redaction modes (mask, replace, hash)
- REQ-003: action='modify' with modified_content as redacted text
- REQ-004: Configurable entity_types list
- REQ-005: Compile regex patterns in initialize()
- REQ-006: details records PII types and counts, no raw values
"""

from __future__ import annotations

import hashlib
import re

import pytest

from z_llm_safety_gateway.detectors.pii import PIIDetector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult


def _ctx() -> DetectionContext:
    """Build a minimal input-direction detection context for tests."""
    return DetectionContext(direction="input", request_id="req-test")


class TestPIIDetection:
    """REQ-001: Detect multiple PII types."""

    async def test_detect_email_and_phone(self) -> None:
        """TC-PII-001: Content with email and phone detects both, category='pii'."""
        detector = PIIDetector()
        await detector.initialize({})

        content = "Contact me at john@example.com or 555-123-4567."
        result = await detector.detect(content, _ctx())

        assert isinstance(result, DetectionResult)
        assert result.category == "pii"
        assert result.details["entities"]["email"] == 1
        assert result.details["entities"]["phone"] == 1

    async def test_detect_ssn_credit_card_ip(self) -> None:
        """TC-PII-006: Content with SSN, credit_card, ip_address detects all three."""
        detector = PIIDetector()
        await detector.initialize({})

        content = "SSN 123-45-6789, card 4532-1234-5678-9012, ip 192.168.1.1"
        result = await detector.detect(content, _ctx())

        assert result.details["entities"]["ssn"] == 1
        assert result.details["entities"]["credit_card"] == 1
        assert result.details["entities"]["ip_address"] == 1
        assert result.details["total_count"] == 3

    async def test_benign_content_returns_allow(self) -> None:
        """TC-PII-007: Benign content returns confidence=0.0, action=allow, no entities."""
        detector = PIIDetector()
        await detector.initialize({})

        content = "Hello world, this is a normal message with no sensitive data."
        result = await detector.detect(content, _ctx())

        assert result.action == "allow"
        assert result.confidence == 0.0
        assert result.risk_level == "low"
        assert result.details["total_count"] == 0
        assert result.details["entities"] == {}
        assert result.modified_content is None


class TestPIIRedactionModes:
    """REQ-002: Redaction modes (mask, replace, hash)."""

    async def test_mask_redaction_mode(self) -> None:
        """TC-PII-002: mask mode masks email, original NOT in modified_content."""
        detector = PIIDetector()
        await detector.initialize({"redaction_mode": "mask"})

        content = "Email: john@example.com"
        result = await detector.detect(content, _ctx())

        assert result.action == "modify"
        assert result.modified_content is not None
        assert "john@example.com" not in result.modified_content
        # Mask preserves email structure: local@domain.tld
        assert "@" in result.modified_content
        assert ".com" in result.modified_content
        assert "*" in result.modified_content

    async def test_replace_redaction_mode(self) -> None:
        """TC-PII-003: replace mode replaces SSN with [REDACTED], original NOT present."""
        detector = PIIDetector()
        await detector.initialize({"redaction_mode": "replace"})

        content = "SSN: 123-45-6789"
        result = await detector.detect(content, _ctx())

        assert result.modified_content is not None
        assert "123-45-6789" not in result.modified_content
        assert "[REDACTED]" in result.modified_content

    async def test_hash_redaction_mode(self) -> None:
        """TC-PII-008: hash mode replaces IP with SHA-256 hash (first 16 chars)."""
        detector = PIIDetector()
        await detector.initialize({"redaction_mode": "hash"})

        content = "Server IP: 192.168.1.1"
        result = await detector.detect(content, _ctx())

        assert result.modified_content is not None
        assert "192.168.1.1" not in result.modified_content
        expected_hash = hashlib.sha256(b"192.168.1.1").hexdigest()[:16]
        assert expected_hash in result.modified_content


class TestPIIModifyAction:
    """REQ-003: action='modify' with modified_content as redacted text."""

    async def test_action_modify_preserves_non_pii(self) -> None:
        """TC-PII-004: action=modify, modified_content fully redacted, preserves non-PII."""
        detector = PIIDetector()
        await detector.initialize({"redaction_mode": "replace"})

        content = "Please email admin@company.org for details."
        result = await detector.detect(content, _ctx())

        assert result.action == "modify"
        assert result.modified_content is not None
        assert "admin@company.org" not in result.modified_content
        assert "[REDACTED]" in result.modified_content
        # Non-PII portions preserved
        assert "Please email" in result.modified_content
        assert "for details." in result.modified_content

    async def test_multiple_pii_all_redacted(self) -> None:
        """TC-PII-009: Multiple PII entities of different types all redacted."""
        detector = PIIDetector()
        await detector.initialize({"redaction_mode": "replace"})

        content = "Email john@test.com, phone 555-123-4567, ssn 123-45-6789"
        result = await detector.detect(content, _ctx())

        assert result.action == "modify"
        assert result.modified_content is not None
        assert "john@test.com" not in result.modified_content
        assert "555-123-4567" not in result.modified_content
        assert "123-45-6789" not in result.modified_content
        assert result.modified_content.count("[REDACTED]") == 3
        assert result.details["total_count"] == 3


class TestPIIInitialize:
    """REQ-005: Compile regex patterns in initialize()."""

    async def test_initialize_compiles_patterns(self) -> None:
        """TC-PII-005: All patterns compiled in initialize(), stored for reuse."""
        detector = PIIDetector()
        await detector.initialize({})

        assert len(detector._patterns) > 0
        for entity_type, pattern in detector._patterns.items():
            assert isinstance(pattern, re.Pattern)
            assert entity_type in (
                "email",
                "phone",
                "ssn",
                "credit_card",
                "ip_address",
            )

    async def test_invalid_regex_raises_valueerror(self) -> None:
        """TC-PII-013: Invalid regex pattern causes initialize() to raise ValueError."""
        detector = PIIDetector()
        with pytest.raises(ValueError):
            await detector.initialize(
                {"custom_patterns": {"bad_type": "[unclosed"}}
            )


class TestPIIEntityTypes:
    """REQ-004: Configurable entity_types list."""

    async def test_entity_types_filters_detection(self) -> None:
        """TC-PII-010: entity_types=['email','phone'] only detects specified, SSN NOT detected."""
        detector = PIIDetector()
        await detector.initialize({"entity_types": ["email", "phone"]})

        content = "Email john@test.com, phone 555-123-4567, ssn 123-45-6789"
        result = await detector.detect(content, _ctx())

        assert "email" in result.details["entities"]
        assert "phone" in result.details["entities"]
        assert "ssn" not in result.details["entities"]
        # SSN value preserved (not redacted) because ssn type is excluded
        assert "123-45-6789" in result.modified_content

    async def test_default_entity_types_detects_all(self) -> None:
        """TC-PII-012: Default (no entity_types) detects all supported types."""
        detector = PIIDetector()
        await detector.initialize({})

        content = (
            "john@test.com 555-123-4567 123-45-6789 "
            "4532-1234-5678-9012 192.168.1.1"
        )
        result = await detector.detect(content, _ctx())

        entities = result.details["entities"]
        assert "email" in entities
        assert "phone" in entities
        assert "ssn" in entities
        assert "credit_card" in entities
        assert "ip_address" in entities
        assert result.details["total_count"] == 5


class TestPIIDetails:
    """REQ-006: details records PII types and counts, no raw values."""

    async def test_details_records_counts_no_raw_values(self) -> None:
        """TC-PII-011: details has entity->count mapping, total count, NO raw PII values."""
        detector = PIIDetector()
        await detector.initialize({})

        content = "john@test.com and jane@test.com and 555-123-4567"
        result = await detector.detect(content, _ctx())

        details = result.details
        assert details["entities"]["email"] == 2
        assert details["entities"]["phone"] == 1
        assert details["total_count"] == 3
        # No raw PII values leaked into details
        details_str = str(details)
        assert "john@test.com" not in details_str
        assert "jane@test.com" not in details_str
        assert "555-123-4567" not in details_str
