"""Tests for SecretLeakDetector: secret and credential leak detection."""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.detectors.secret_leak import SecretLeakDetector
from z_llm_safety_gateway.models import DetectionContext

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

API_KEY_SECRET = "sk-1234567890abcdef1234567890abcdef"
API_KEY_CONTENT = f"Please use my key: {API_KEY_SECRET} for the API call."

PRIVATE_KEY_CONTENT = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."

JWT_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
JWT_CONTENT = f"Authorization: Bearer {JWT_TOKEN}"

AWS_ACCESS_KEY = "AKIA1234567890ABCDEF"
AWS_CONTENT = f"aws_access_key_id = {AWS_ACCESS_KEY}"

BENIGN_CONTENT = "The quick brown fox jumps over the lazy dog"

INTERNAL_TOKEN_VALUE = "int_a1b2c3d4e5f6789012345678901234ab"
INTERNAL_TOKEN_CONTENT = f"Use this token: {INTERNAL_TOKEN_VALUE}"


def _make_context() -> DetectionContext:
    """Create a minimal DetectionContext for testing."""
    return DetectionContext(direction="input", request_id="req-test-001")


# ---------------------------------------------------------------------------
# REQ-001: Detect multiple secret types (api_key, aws_secret, private_key, jwt_token)
# ---------------------------------------------------------------------------


class TestSecretLeakDetectMultipleTypes:
    """REQ-001: Detect api_key, aws_secret, private_key, and jwt_token."""

    async def test_tc_sec_001_detects_api_key(self) -> None:
        """TC-SEC-001: Content with OpenAI-style API key is detected."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(API_KEY_CONTENT, _make_context())

        assert result.detector_name == "secret_leak"
        assert result.category == "secret_leak"
        assert "api_key" in result.details["secrets"]
        assert result.details["secrets"]["api_key"] >= 1

    async def test_tc_sec_002_detects_private_key(self) -> None:
        """TC-SEC-002: Content with PEM private key header is detected."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(PRIVATE_KEY_CONTENT, _make_context())

        assert result.category == "secret_leak"
        assert "private_key" in result.details["secrets"]
        assert result.details["secrets"]["private_key"] >= 1

    async def test_tc_sec_003_detects_jwt_token(self) -> None:
        """TC-SEC-003: Content with JWT token is detected."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(JWT_CONTENT, _make_context())

        assert result.category == "secret_leak"
        assert "jwt_token" in result.details["secrets"]
        assert result.details["secrets"]["jwt_token"] >= 1

    async def test_tc_sec_011_default_patterns_detect_all_types(self) -> None:
        """TC-SEC-011: Default config (no patterns list) detects all 4 secret types."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        test_cases = [
            (API_KEY_CONTENT, "api_key"),
            (AWS_CONTENT, "aws_secret"),
            (PRIVATE_KEY_CONTENT, "private_key"),
            (JWT_CONTENT, "jwt_token"),
        ]

        for content, expected_type in test_cases:
            result = await detector.detect(content, _make_context())
            assert result.category == "secret_leak", (
                f"Expected '{expected_type}' to be detected with default patterns"
            )
            assert expected_type in result.details["secrets"], (
                f"Expected '{expected_type}' in secrets for content"
            )


# ---------------------------------------------------------------------------
# REQ-002: Configurable patterns list
# ---------------------------------------------------------------------------


class TestSecretLeakConfigurablePatterns:
    """REQ-002: Configurable patterns list controls which patterns are active."""

    async def test_tc_sec_007_custom_patterns_list_excludes_others(self) -> None:
        """TC-SEC-007: Patterns list with only api_key and jwt_token -> AWS NOT detected."""
        detector = SecretLeakDetector()
        await detector.initialize({"patterns": ["api_key", "jwt_token"]})

        result = await detector.detect(AWS_CONTENT, _make_context())

        assert result.confidence == 0.0
        assert result.action == "allow"
        assert "aws_secret" not in result.details.get("secrets", {})

    async def test_custom_patterns_list_still_detects_specified(self) -> None:
        """Patterns list with api_key still detects that type."""
        detector = SecretLeakDetector()
        await detector.initialize({"patterns": ["api_key", "jwt_token"]})

        result = await detector.detect(API_KEY_CONTENT, _make_context())

        assert "api_key" in result.details["secrets"]
        assert result.action == "block"


# ---------------------------------------------------------------------------
# REQ-003: action='block' when secrets detected
# ---------------------------------------------------------------------------


class TestSecretLeakBlockAction:
    """REQ-003: Detected secret -> action='block'; no secret -> action='allow'."""

    async def test_tc_sec_004_detected_secret_action_is_block(self) -> None:
        """TC-SEC-004: At least one secret matched -> action='block', confidence > 0."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(API_KEY_CONTENT, _make_context())

        assert result.action == "block"
        assert result.confidence > 0.0
        assert result.risk_level == "critical"

    async def test_tc_sec_006_benign_content_confidence_zero(self) -> None:
        """TC-SEC-006: Benign content returns confidence=0.0, action='allow'."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(BENIGN_CONTENT, _make_context())

        assert result.confidence == 0.0
        assert result.action == "allow"
        assert result.risk_level == "low"
        assert result.message == "No secrets detected"

    async def test_tc_sec_008_no_secret_match_action_allow(self) -> None:
        """TC-SEC-008: No secrets matched -> action='allow', confidence=0.0."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(
            "This is a normal message with no secrets.", _make_context()
        )

        assert result.action == "allow"
        assert result.confidence == 0.0

    async def test_block_message_includes_count_and_types(self) -> None:
        """Block message follows format: 'Detected N potential secret(s) of type(s): X, Y'."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        result = await detector.detect(API_KEY_CONTENT, _make_context())

        assert "Detected" in result.message
        assert "potential secret(s)" in result.message
        assert "api_key" in result.message


# ---------------------------------------------------------------------------
# REQ-004: Compile regex patterns in initialize()
# ---------------------------------------------------------------------------


class TestSecretLeakInitialize:
    """REQ-004: initialize() compiles regex patterns; invalid regex raises error."""

    async def test_tc_sec_005_initialize_compiles_patterns(self) -> None:
        """TC-SEC-005: All patterns compiled in initialize(), stored for reuse."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        assert hasattr(detector, "_compiled_patterns")
        assert len(detector._compiled_patterns) == 4

        expected_names = {"api_key", "aws_secret", "private_key", "jwt_token"}
        assert set(detector._compiled_patterns.keys()) == expected_names

        for pattern in detector._compiled_patterns.values():
            assert hasattr(pattern, "search")

    async def test_tc_sec_012_invalid_regex_raises_error(self) -> None:
        """TC-SEC-012: Invalid regex pattern causes initialize() to raise ValueError."""
        detector = SecretLeakDetector()

        with pytest.raises(ValueError, match="(?i)invalid"):
            await detector.initialize(
                {"custom_patterns": {"bad_pattern": "[invalid(regex"}}
            )


# ---------------------------------------------------------------------------
# REQ-005: details records secret types and counts
# ---------------------------------------------------------------------------


class TestSecretLeakDetails:
    """REQ-005: details records secret types and counts, no raw values."""

    async def test_tc_sec_009_details_has_counts_and_no_raw_values(self) -> None:
        """TC-SEC-009: details has secret type->count, total_count, and NO raw secret values."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        content = f"Key: {API_KEY_SECRET} and token: {JWT_TOKEN}"
        result = await detector.detect(content, _make_context())

        details = result.details
        assert "secrets" in details
        assert "total_count" in details
        assert isinstance(details["secrets"], dict)
        assert details["total_count"] >= 2
        assert "api_key" in details["secrets"]
        assert "jwt_token" in details["secrets"]

        # No raw secret values should appear anywhere in details
        details_str = str(details)
        assert API_KEY_SECRET not in details_str
        assert JWT_TOKEN not in details_str

    async def test_details_total_count_matches_sum(self) -> None:
        """details total_count equals the sum of individual type counts."""
        detector = SecretLeakDetector()
        await detector.initialize({})

        content = f"Key1: {API_KEY_SECRET} Key2: sk-abcdefghijklmnopqrstuvwxyz123456"
        result = await detector.detect(content, _make_context())

        secrets = result.details["secrets"]
        expected_total = sum(secrets.values())
        assert result.details["total_count"] == expected_total


# ---------------------------------------------------------------------------
# REQ-006: Support custom regex patterns
# ---------------------------------------------------------------------------


class TestSecretLeakCustomRegex:
    """REQ-006: Support custom regex patterns and override defaults."""

    async def test_tc_sec_010_custom_regex_pattern_detected(self) -> None:
        """TC-SEC-010: Custom pattern 'internal_token' with regex 'int_[a-f0-9]{32}' detected."""
        detector = SecretLeakDetector()
        await detector.initialize(
            {"custom_patterns": {"internal_token": "int_[a-f0-9]{32}"}}
        )

        result = await detector.detect(INTERNAL_TOKEN_CONTENT, _make_context())

        assert result.action == "block"
        assert "internal_token" in result.details["secrets"]

    async def test_tc_sec_013_custom_pattern_overrides_default(self) -> None:
        """TC-SEC-013: Custom pattern with same name as default replaces it."""
        detector = SecretLeakDetector()
        await detector.initialize(
            {"custom_patterns": {"api_key": "OVERRIDE-[a-z]+"}}
        )

        # New custom pattern should match
        result_new = await detector.detect("Found OVERRIDE-test key", _make_context())
        assert result_new.action == "block"
        assert "api_key" in result_new.details["secrets"]

        # Old default pattern (sk-...) should no longer match
        result_old = await detector.detect(API_KEY_CONTENT, _make_context())
        assert result_old.action == "allow"
        assert result_old.confidence == 0.0

    async def test_custom_pattern_added_alongside_defaults(self) -> None:
        """Custom pattern is added in addition to default patterns."""
        detector = SecretLeakDetector()
        await detector.initialize(
            {"custom_patterns": {"internal_token": "int_[a-f0-9]{32}"}}
        )

        # Defaults still work
        result_default = await detector.detect(API_KEY_CONTENT, _make_context())
        assert "api_key" in result_default.details["secrets"]

        # Custom pattern also works
        result_custom = await detector.detect(INTERNAL_TOKEN_CONTENT, _make_context())
        assert "internal_token" in result_custom.details["secrets"]
