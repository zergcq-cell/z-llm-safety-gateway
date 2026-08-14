"""Unit tests for the z_llm_safety_gateway_sdk package (TC-SDK-001/002/006).

Test cases:
- TC-SDK-001: SDK package structure complete (base/context/result/modification/testing + re-exports)
- TC-SDK-002: SDK Detector/DetectionResult/DetectionContext interface matches gateway
- TC-SDK-006: SDK testing utils (make_context + assertion helpers)
"""

from __future__ import annotations

import pytest
import z_llm_safety_gateway_sdk as sdk
from z_llm_safety_gateway_sdk.base import Detector
from z_llm_safety_gateway_sdk.context import DetectionContext
from z_llm_safety_gateway_sdk.modification import Modification
from z_llm_safety_gateway_sdk.result import DetectionResult
from z_llm_safety_gateway_sdk.testing import (
    assert_allowed,
    assert_blocked,
    assert_confidence,
    make_context,
)


# --------------------------------------------------------------------------- #
# TC-SDK-001: SDK package structure
# --------------------------------------------------------------------------- #
def test_sdk_reexports_core_types() -> None:
    """TC-SDK-001: SDK package re-exports core types from __init__."""
    assert sdk.Detector is Detector
    assert sdk.DetectionContext is DetectionContext
    assert sdk.DetectionResult is DetectionResult
    assert sdk.Modification is Modification


def test_sdk_has_independent_version() -> None:
    """TC-SDK-001b: SDK has its own version independent of the gateway."""
    assert sdk.__version__ == "1.0.0"


# --------------------------------------------------------------------------- #
# TC-SDK-002: SDK interface matches gateway
# --------------------------------------------------------------------------- #
def test_sdk_detector_interface_matches_gateway() -> None:
    """TC-SDK-002: SDK Detector requires name/category/description/version
    class attrs and async initialize/detect methods (mirrors gateway)."""

    class MyDetector(Detector):
        name = "my_detector"
        category = "custom"
        description = "test"
        version = "1.0.0"

        async def initialize(self, config: dict) -> None:
            self._threshold = config.get("threshold", 0.8)

        async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
            return DetectionResult(
                detector_name=self.name,
                category=self.category,
                action="allow",
                confidence=0.1,
                risk_level="low",
                message="ok",
            )

    d = MyDetector()
    assert d.name == "my_detector"
    assert d.category == "custom"
    assert d.version == "1.0.0"


def test_sdk_detector_is_abstract() -> None:
    """TC-SDK-002b: Detector base cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Detector()  # type: ignore[abstract]


def test_sdk_detection_context_fields_match_gateway() -> None:
    """TC-SDK-002c: DetectionContext has direction/request_id/user_id/metadata/
    language/message_index fields (gateway-compatible)."""
    ctx = make_context(
        direction="input",
        user_id="u1",
        metadata={"k": "v"},
        language="en",
        message_index=0,
    )
    assert ctx.direction == "input"
    assert ctx.request_id.startswith("req_")
    assert ctx.user_id == "u1"
    assert ctx.metadata == {"k": "v"}
    assert ctx.language == "en"
    assert ctx.message_index == 0


def test_sdk_detection_result_fields_match_gateway() -> None:
    """TC-SDK-002d: DetectionResult has gateway-compatible fields."""
    result = DetectionResult(
        detector_name="d",
        category="c",
        action="block",
        confidence=0.95,
        risk_level="high",
        message="blocked",
        details={"rule": "r1"},
    )
    assert result.detector_name == "d"
    assert result.category == "c"
    assert result.action == "block"
    assert result.confidence == 0.95
    assert result.risk_level == "high"
    assert result.details == {"rule": "r1"}
    assert result.modified_content is None
    assert result.to_dict()["action"] == "block"


def test_sdk_result_validates_confidence_range() -> None:
    """TC-SDK-002e: DetectionResult rejects confidence outside [0, 1]."""
    with pytest.raises(ValueError):
        DetectionResult(
            detector_name="d",
            category="c",
            action="allow",
            confidence=1.5,
            risk_level="low",
            message="bad",
        )


# --------------------------------------------------------------------------- #
# TC-SDK-006: SDK testing utilities
# --------------------------------------------------------------------------- #
def test_make_context_defaults() -> None:
    """TC-SDK-006: make_context provides defaults (direction=input, auto request_id)."""
    ctx = make_context()
    assert ctx.direction == "input"
    assert ctx.request_id.startswith("req_")
    assert ctx.user_id is None
    assert ctx.metadata == {}
    assert ctx.language is None


def test_assert_helpers() -> None:
    """TC-SDK-006b: assertion helpers validate action/risk_level/confidence."""
    ok = DetectionResult(
        detector_name="d", category="c", action="allow",
        confidence=0.1, risk_level="low", message="ok",
    )
    blocked = DetectionResult(
        detector_name="d", category="c", action="block",
        confidence=0.9, risk_level="critical", message="no",
    )
    assert_allowed(ok)
    assert_blocked(blocked)
    assert_confidence(blocked, minimum=0.5)
