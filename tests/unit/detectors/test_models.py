"""Tests for DetectionResult and DetectionContext Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from z_llm_safety_gateway.models import DetectionContext, DetectionResult


class TestDetectionResultModel:
    """REQ-007: DetectionResult data model field definitions and validation."""

    def test_detection_result_has_all_required_fields(self) -> None:
        """DetectionResult can be created with all required fields."""
        result = DetectionResult(
            detector_name="pii_detector",
            category="pii",
            action="block",
            confidence=0.95,
            risk_level="high",
            message="Detected SSN in content",
        )

        assert result.detector_name == "pii_detector"
        assert result.category == "pii"
        assert result.action == "block"
        assert result.confidence == 0.95
        assert result.risk_level == "high"
        assert result.message == "Detected SSN in content"

    def test_detection_result_is_basemodel_subclass(self) -> None:
        """DetectionResult should be a Pydantic BaseModel."""
        assert issubclass(DetectionResult, BaseModel)

    def test_detection_result_default_details_is_empty_dict(self) -> None:
        """details field defaults to an empty dict."""
        result = DetectionResult(
            detector_name="test",
            category="test",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )
        assert result.details == {}
        assert isinstance(result.details, dict)

    def test_detection_result_default_modified_content_is_none(self) -> None:
        """modified_content defaults to None."""
        result = DetectionResult(
            detector_name="test",
            category="test",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )
        assert result.modified_content is None

    def test_detection_result_default_duration_ms_is_zero(self) -> None:
        """duration_ms defaults to 0.0."""
        result = DetectionResult(
            detector_name="test",
            category="test",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )
        assert result.duration_ms == 0.0
        assert isinstance(result.duration_ms, float)

    def test_detection_result_default_error_is_none(self) -> None:
        """error defaults to None."""
        result = DetectionResult(
            detector_name="test",
            category="test",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )
        assert result.error is None

    def test_detection_result_action_allow_is_valid(self) -> None:
        """action 'allow' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.1, risk_level="low", message="m",
        )
        assert result.action == "allow"

    def test_detection_result_action_block_is_valid(self) -> None:
        """action 'block' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="block",
            confidence=0.9, risk_level="high", message="m",
        )
        assert result.action == "block"

    def test_detection_result_action_flag_is_valid(self) -> None:
        """action 'flag' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="flag",
            confidence=0.5, risk_level="medium", message="m",
        )
        assert result.action == "flag"

    def test_detection_result_action_modify_is_valid(self) -> None:
        """action 'modify' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="modify",
            confidence=0.7, risk_level="medium", message="m",
            modified_content="redacted",
        )
        assert result.action == "modify"
        assert result.modified_content == "redacted"

    def test_detection_result_invalid_action_raises_error(self) -> None:
        """action must be one of allow/block/flag/modify."""
        with pytest.raises(ValidationError):
            DetectionResult(
                detector_name="t", category="t", action="invalid_action",
                confidence=0.5, risk_level="low", message="m",
            )

    def test_detection_result_risk_level_low_is_valid(self) -> None:
        """risk_level 'low' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.1, risk_level="low", message="m",
        )
        assert result.risk_level == "low"

    def test_detection_result_risk_level_medium_is_valid(self) -> None:
        """risk_level 'medium' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="flag",
            confidence=0.4, risk_level="medium", message="m",
        )
        assert result.risk_level == "medium"

    def test_detection_result_risk_level_high_is_valid(self) -> None:
        """risk_level 'high' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="block",
            confidence=0.8, risk_level="high", message="m",
        )
        assert result.risk_level == "high"

    def test_detection_result_risk_level_critical_is_valid(self) -> None:
        """risk_level 'critical' is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="block",
            confidence=1.0, risk_level="critical", message="m",
        )
        assert result.risk_level == "critical"

    def test_detection_result_invalid_risk_level_raises_error(self) -> None:
        """risk_level must be one of low/medium/high/critical."""
        with pytest.raises(ValidationError):
            DetectionResult(
                detector_name="t", category="t", action="allow",
                confidence=0.1, risk_level="extreme", message="m",
            )

    @pytest.mark.parametrize("confidence", [0.0, 0.1, 0.5, 0.9, 1.0])
    def test_detection_result_confidence_in_range_is_valid(
        self, confidence: float
    ) -> None:
        """confidence between 0.0 and 1.0 (inclusive) is valid."""
        result = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=confidence, risk_level="low", message="m",
        )
        assert result.confidence == confidence

    @pytest.mark.parametrize("confidence", [-0.01, 1.01, -1.0, 2.0])
    def test_detection_result_confidence_out_of_range_raises_error(
        self, confidence: float
    ) -> None:
        """confidence outside [0.0, 1.0] raises ValidationError."""
        with pytest.raises(ValidationError):
            DetectionResult(
                detector_name="t", category="t", action="allow",
                confidence=confidence, risk_level="low", message="m",
            )

    def test_detection_result_details_can_be_set(self) -> None:
        """details field can be set with custom dict."""
        result = DetectionResult(
            detector_name="t", category="t", action="flag",
            confidence=0.5, risk_level="medium", message="m",
            details={"count": 3, "matches": ["a", "b"]},
        )
        assert result.details["count"] == 3
        assert result.details["matches"] == ["a", "b"]

    def test_detection_result_modified_content_can_be_set(self) -> None:
        """modified_content can be set to a string."""
        result = DetectionResult(
            detector_name="t", category="t", action="modify",
            confidence=0.7, risk_level="medium", message="m",
            modified_content="sanitized text",
        )
        assert result.modified_content == "sanitized text"

    def test_detection_result_duration_ms_can_be_set(self) -> None:
        """duration_ms can be set to a float."""
        result = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.1, risk_level="low", message="m",
            duration_ms=12.5,
        )
        assert result.duration_ms == 12.5

    def test_detection_result_error_can_be_set(self) -> None:
        """error can be set to a string."""
        result = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.0, risk_level="low", message="m",
            error="model load failed",
        )
        assert result.error == "model load failed"

    def test_detection_result_each_instance_has_independent_details(self) -> None:
        """details default should not be shared between instances."""
        r1 = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.0, risk_level="low", message="m",
        )
        r2 = DetectionResult(
            detector_name="t", category="t", action="allow",
            confidence=0.0, risk_level="low", message="m",
        )
        r1.details["key"] = "value"
        assert "key" not in r2.details


class TestDetectionContextModel:
    """REQ-006: DetectionContext data model field definitions and validation."""

    def test_detection_context_has_required_fields(self) -> None:
        """DetectionContext can be created with direction and request_id."""
        ctx = DetectionContext(direction="input", request_id="req-123")

        assert ctx.direction == "input"
        assert ctx.request_id == "req-123"

    def test_detection_context_is_basemodel_subclass(self) -> None:
        """DetectionContext should be a Pydantic BaseModel."""
        assert issubclass(DetectionContext, BaseModel)

    def test_detection_context_default_user_id_is_none(self) -> None:
        """user_id defaults to None."""
        ctx = DetectionContext(direction="input", request_id="req-1")
        assert ctx.user_id is None

    def test_detection_context_default_metadata_is_empty_dict(self) -> None:
        """metadata defaults to an empty dict."""
        ctx = DetectionContext(direction="input", request_id="req-1")
        assert ctx.metadata == {}
        assert isinstance(ctx.metadata, dict)

    def test_detection_context_default_language_is_none(self) -> None:
        """language defaults to None."""
        ctx = DetectionContext(direction="input", request_id="req-1")
        assert ctx.language is None

    def test_detection_context_default_message_index_is_none(self) -> None:
        """message_index defaults to None."""
        ctx = DetectionContext(direction="output", request_id="req-1")
        assert ctx.message_index is None

    def test_detection_context_direction_input_is_valid(self) -> None:
        """direction 'input' is valid."""
        ctx = DetectionContext(direction="input", request_id="req-1")
        assert ctx.direction == "input"

    def test_detection_context_direction_output_is_valid(self) -> None:
        """direction 'output' is valid."""
        ctx = DetectionContext(direction="output", request_id="req-1")
        assert ctx.direction == "output"

    def test_detection_context_invalid_direction_raises_error(self) -> None:
        """direction must be 'input' or 'output'."""
        with pytest.raises(ValidationError):
            DetectionContext(direction="sideways", request_id="req-1")

    def test_detection_context_user_id_can_be_set(self) -> None:
        """user_id can be set to a string."""
        ctx = DetectionContext(
            direction="input", request_id="req-1", user_id="user-abc"
        )
        assert ctx.user_id == "user-abc"

    def test_detection_context_metadata_can_be_set(self) -> None:
        """metadata can be set with custom dict."""
        ctx = DetectionContext(
            direction="input", request_id="req-1",
            metadata={"source": "api", "version": 2},
        )
        assert ctx.metadata["source"] == "api"
        assert ctx.metadata["version"] == 2

    def test_detection_context_language_can_be_set(self) -> None:
        """language can be set to a string."""
        ctx = DetectionContext(
            direction="input", request_id="req-1", language="en"
        )
        assert ctx.language == "en"

    def test_detection_context_message_index_can_be_set(self) -> None:
        """message_index can be set to an int."""
        ctx = DetectionContext(
            direction="input", request_id="req-1", message_index=3
        )
        assert ctx.message_index == 3
        assert isinstance(ctx.message_index, int)

    def test_detection_context_message_index_can_be_none(self) -> None:
        """message_index can be None (output direction)."""
        ctx = DetectionContext(
            direction="output", request_id="req-1", message_index=None
        )
        assert ctx.message_index is None

    def test_detection_context_each_instance_has_independent_metadata(self) -> None:
        """metadata default should not be shared between instances."""
        c1 = DetectionContext(direction="input", request_id="r1")
        c2 = DetectionContext(direction="input", request_id="r2")
        c1.metadata["key"] = "value"
        assert "key" not in c2.metadata

    def test_detection_context_all_fields_set(self) -> None:
        """DetectionContext can be created with all fields populated."""
        ctx = DetectionContext(
            direction="input",
            request_id="req-full",
            user_id="user-1",
            metadata={"ip": "10.0.0.1"},
            language="zh",
            message_index=2,
        )
        assert ctx.direction == "input"
        assert ctx.request_id == "req-full"
        assert ctx.user_id == "user-1"
        assert ctx.metadata == {"ip": "10.0.0.1"}
        assert ctx.language == "zh"
        assert ctx.message_index == 2
