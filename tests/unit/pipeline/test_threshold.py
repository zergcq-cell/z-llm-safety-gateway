"""Unit tests for ThresholdDecisionEngine — TC-INJ-003/004, TC-TOX-004/005.

Covers the threshold-driven decision engine that maps a detector's confidence
score to an action (block / flag / allow) using per-detector thresholds, as
specified in design.md Decision 5 and DESIGN.md Section 5.3.
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.pipeline.threshold import ThresholdDecisionEngine


class TestThresholdDecision:
    """REQ-005 (Decision 5): confidence → action via thresholds."""

    @pytest.mark.parametrize(
        ("confidence", "block_threshold", "flag_threshold", "expected"),
        [
            # block: confidence >= block_threshold
            (0.90, 0.85, 0.50, "block"),
            (0.85, 0.85, 0.50, "block"),  # boundary: exactly at block_threshold
            (1.0, 0.85, 0.50, "block"),  # max confidence
            # flag: flag_threshold <= confidence < block_threshold
            (0.50, 0.85, 0.50, "flag"),  # boundary: exactly at flag_threshold
            (0.75, 0.85, 0.50, "flag"),  # middle of flag range
            (0.84, 0.85, 0.50, "flag"),  # just below block_threshold
            # allow: confidence < flag_threshold
            (0.0, 0.85, 0.50, "allow"),  # zero confidence
            (0.49, 0.85, 0.50, "allow"),  # just below flag_threshold
        ],
    )
    def test_threshold_decision_boundaries(
        self,
        confidence: float,
        block_threshold: float,
        flag_threshold: float,
        expected: str,
    ) -> None:
        """Parametrized: confidence maps to correct action at threshold boundaries."""
        result = ThresholdDecisionEngine.decide(
            confidence, block_threshold, flag_threshold
        )
        assert result == expected

    def test_block_when_confidence_exceeds_block_threshold(self) -> None:
        """confidence >= block_threshold → 'block'."""
        result = ThresholdDecisionEngine.decide(0.95, 0.90, 0.60)
        assert result == "block"

    def test_flag_when_confidence_between_thresholds(self) -> None:
        """flag_threshold <= confidence < block_threshold → 'flag'."""
        result = ThresholdDecisionEngine.decide(0.70, 0.90, 0.60)
        assert result == "flag"

    def test_allow_when_confidence_below_flag_threshold(self) -> None:
        """confidence < flag_threshold → 'allow'."""
        result = ThresholdDecisionEngine.decide(0.30, 0.90, 0.60)
        assert result == "allow"

    def test_block_takes_precedence_over_flag(self) -> None:
        """When confidence >= both thresholds, block wins."""
        result = ThresholdDecisionEngine.decide(0.95, 0.90, 0.90)
        assert result == "block"

    def test_return_type_is_string(self) -> None:
        """The returned action is a string."""
        result = ThresholdDecisionEngine.decide(0.5, 0.9, 0.3)
        assert isinstance(result, str)

    def test_can_be_called_as_static_method(self) -> None:
        """decide() works as a static method without instantiation."""
        # No instance needed
        assert ThresholdDecisionEngine.decide(1.0, 0.5, 0.3) == "block"

    def test_can_be_called_via_instance(self) -> None:
        """decide() also works when called via an instance."""
        engine = ThresholdDecisionEngine()
        assert engine.decide(1.0, 0.5, 0.3) == "block"

    def test_different_threshold_pairs_are_independent(self) -> None:
        """Different threshold pairs produce independent decisions."""
        # Same confidence, different thresholds
        assert ThresholdDecisionEngine.decide(0.70, 0.90, 0.60) == "flag"
        assert ThresholdDecisionEngine.decide(0.70, 0.60, 0.50) == "block"
        assert ThresholdDecisionEngine.decide(0.70, 0.90, 0.80) == "allow"

    def test_zero_confidence_always_allow(self) -> None:
        """confidence=0.0 always returns 'allow' (unless flag_threshold=0.0)."""
        assert ThresholdDecisionEngine.decide(0.0, 0.85, 0.50) == "allow"
        assert ThresholdDecisionEngine.decide(0.0, 1.0, 0.1) == "allow"

    def test_max_confidence_always_block(self) -> None:
        """confidence=1.0 returns 'block' when block_threshold <= 1.0."""
        assert ThresholdDecisionEngine.decide(1.0, 0.85, 0.50) == "block"
        assert ThresholdDecisionEngine.decide(1.0, 1.0, 0.50) == "block"
