"""Unit tests for ResultAggregator — TC-PIPE-003/004/008/009/013/014.

Covers the result aggregation strategy as specified in design.md Decision 6
and DESIGN.md Section 5.5:

- final_action priority: block > modify > flag > allow
- overall_risk_level: critical > high > medium > low
- modifications: from modify results, sorted by detector priority
- risk_profile: all flag results collected for audit
- Flag escalation: optional upgrade from flag → block
"""

from __future__ import annotations

from z_llm_safety_gateway.models import DetectionResult
from z_llm_safety_gateway.pipeline.aggregator import ResultAggregator
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _result(
    detector_name: str = "det",
    action: str = "allow",
    confidence: float = 0.0,
    risk_level: str = "low",
    modified_content: str | None = None,
    category: str = "test",
) -> DetectionResult:
    """Create a DetectionResult for testing."""
    return DetectionResult(
        detector_name=detector_name,
        category=category,
        action=action,
        confidence=confidence,
        risk_level=risk_level,
        message="test result",
        modified_content=modified_content,
    )


# --------------------------------------------------------------------------- #
# final_action priority
# --------------------------------------------------------------------------- #


class TestFinalActionPriority:
    """REQ-004 SC-001/002: final_action = max precedence (block > modify > flag > allow)."""

    def test_all_allow_returns_allow(self) -> None:
        """All allow results → final_action = allow."""
        results = [_result("a", "allow"), _result("b", "allow")]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "allow"

    def test_flag_plus_allow_returns_flag(self) -> None:
        """TC-PIPE-008: flag + allow → final_action = flag."""
        results = [_result("a", "flag"), _result("b", "allow")]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "flag"

    def test_modify_plus_flag_plus_allow_returns_modify(self) -> None:
        """TC-PIPE-003: modify + flag + allow → final_action = modify."""
        results = [
            _result("a", "allow"),
            _result("b", "flag"),
            _result("c", "modify", modified_content="redacted"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "modify"

    def test_block_plus_modify_plus_flag_plus_allow_returns_block(self) -> None:
        """block takes precedence over all other actions."""
        results = [
            _result("a", "allow"),
            _result("b", "flag"),
            _result("c", "modify", modified_content="redacted"),
            _result("d", "block"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "block"

    def test_block_over_modify(self) -> None:
        """block > modify."""
        results = [
            _result("a", "modify", modified_content="redacted"),
            _result("b", "block"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "block"

    def test_modify_over_flag(self) -> None:
        """modify > flag."""
        results = [
            _result("a", "flag"),
            _result("b", "modify", modified_content="redacted"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "modify"

    def test_empty_results_returns_allow(self) -> None:
        """No results → final_action = allow (default)."""
        agg = ResultAggregator().aggregate([])
        assert agg.final_action == "allow"

    def test_single_block(self) -> None:
        """A single block result → final_action = block."""
        results = [_result("a", "block")]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "block"


# --------------------------------------------------------------------------- #
# overall_risk_level
# --------------------------------------------------------------------------- #


class TestOverallRiskLevel:
    """REQ-005 SC-001: overall_risk_level = highest among all results."""

    def test_low_medium_high_returns_high(self) -> None:
        """TC-PIPE-004: low + medium + high → overall_risk_level = high."""
        results = [
            _result("a", "allow", risk_level="low"),
            _result("b", "flag", risk_level="medium"),
            _result("c", "flag", risk_level="high"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.overall_risk_level == "high"

    def test_critical_is_highest(self) -> None:
        """critical > high > medium > low."""
        results = [
            _result("a", risk_level="low"),
            _result("b", risk_level="medium"),
            _result("c", risk_level="high"),
            _result("d", risk_level="critical"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.overall_risk_level == "critical"

    def test_risk_level_reflects_even_when_action_allow(self) -> None:
        """Even if final_action is allow, overall_risk_level reflects highest."""
        results = [
            _result("a", "allow", risk_level="low"),
            _result("b", "allow", risk_level="high"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert agg.final_action == "allow"
        assert agg.overall_risk_level == "high"

    def test_all_low_returns_low(self) -> None:
        """All low risk → overall_risk_level = low."""
        results = [_result("a", risk_level="low"), _result("b", risk_level="low")]
        agg = ResultAggregator().aggregate(results)
        assert agg.overall_risk_level == "low"

    def test_empty_results_returns_low(self) -> None:
        """No results → overall_risk_level = low (default)."""
        agg = ResultAggregator().aggregate([])
        assert agg.overall_risk_level == "low"


# --------------------------------------------------------------------------- #
# modifications sorting
# --------------------------------------------------------------------------- #


class TestModificationsSorting:
    """REQ-006 SC-001: modifications sorted by detector priority (ascending)."""

    def test_modifications_sorted_by_priority(self) -> None:
        """TC-PIPE-009: modifications sorted by priority ascending."""
        results = [
            _result("sensitive_words", "modify", modified_content="censored"),
            _result("pii", "modify", modified_content="redacted"),
        ]
        priorities = {"pii": 10, "sensitive_words": 20}
        agg = ResultAggregator().aggregate(results, priorities=priorities)
        assert len(agg.modifications) == 2
        # PII (priority=10) should come before sensitive_words (priority=20)
        assert agg.modifications[0].detector_name == "pii"
        assert agg.modifications[1].detector_name == "sensitive_words"

    def test_modifications_include_all_fields(self) -> None:
        """Each Modification includes detector_name, modified_content, priority, message_index."""
        results = [_result("pii", "modify", modified_content="redacted")]
        priorities = {"pii": 10}
        msg_indices = [2]
        agg = ResultAggregator().aggregate(
            results, priorities=priorities, message_indices=msg_indices
        )
        assert len(agg.modifications) == 1
        mod = agg.modifications[0]
        assert mod.detector_name == "pii"
        assert mod.modified_content == "redacted"
        assert mod.priority == 10
        assert mod.message_index == 2

    def test_modify_without_modified_content_excluded(self) -> None:
        """A modify result without modified_content is not included in modifications."""
        results = [_result("det", "modify", modified_content=None)]
        agg = ResultAggregator().aggregate(results)
        assert len(agg.modifications) == 0

    def test_non_modify_results_excluded_from_modifications(self) -> None:
        """Only modify results produce modifications."""
        results = [
            _result("a", "allow"),
            _result("b", "flag"),
            _result("c", "block"),
            _result("d", "modify", modified_content="redacted"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert len(agg.modifications) == 1
        assert agg.modifications[0].detector_name == "d"

    def test_default_priority_when_not_specified(self) -> None:
        """Missing priority defaults to 100."""
        results = [_result("det", "modify", modified_content="redacted")]
        agg = ResultAggregator().aggregate(results)
        assert len(agg.modifications) == 1
        assert agg.modifications[0].priority == 100

    def test_same_priority_preserves_input_order(self) -> None:
        """When priorities are equal, input order is preserved (stable sort)."""
        results = [
            _result("det_a", "modify", modified_content="a"),
            _result("det_b", "modify", modified_content="b"),
        ]
        priorities = {"det_a": 50, "det_b": 50}
        agg = ResultAggregator().aggregate(results, priorities=priorities)
        assert agg.modifications[0].detector_name == "det_a"
        assert agg.modifications[1].detector_name == "det_b"

    def test_message_index_none_when_not_provided(self) -> None:
        """message_index defaults to None when not provided."""
        results = [_result("det", "modify", modified_content="redacted")]
        agg = ResultAggregator().aggregate(results)
        assert agg.modifications[0].message_index is None


# --------------------------------------------------------------------------- #
# risk_profile
# --------------------------------------------------------------------------- #


class TestRiskProfile:
    """Risk profile collects all flag results for audit logging."""

    def test_risk_profile_contains_flag_results(self) -> None:
        """risk_profile includes all flag DetectionResults."""
        flag1 = _result("a", "flag", risk_level="medium", category="pii")
        flag2 = _result("b", "flag", risk_level="high", category="toxicity")
        results = [
            _result("c", "allow"),
            flag1,
            flag2,
            _result("d", "block"),
        ]
        agg = ResultAggregator().aggregate(results)
        assert len(agg.risk_profile) == 2
        assert flag1 in agg.risk_profile
        assert flag2 in agg.risk_profile

    def test_risk_profile_empty_when_no_flags(self) -> None:
        """risk_profile is empty when there are no flag results."""
        results = [_result("a", "allow"), _result("b", "block")]
        agg = ResultAggregator().aggregate(results)
        assert len(agg.risk_profile) == 0


# --------------------------------------------------------------------------- #
# Flag escalation
# --------------------------------------------------------------------------- #


class TestFlagEscalation:
    """REQ-007 SC-001/002: optional flag-to-block escalation."""

    def test_flag_escalated_to_block_when_rule_satisfied(self) -> None:
        """TC-PIPE-013: flag → block when escalation rule is satisfied."""
        rule = FlagEscalationRule("count >= 3 and max_risk_level >= medium")
        aggregator = ResultAggregator(flag_escalation=rule)
        results = [
            _result("a", "flag", risk_level="medium", category="pii"),
            _result("b", "flag", risk_level="medium", category="toxicity"),
            _result("c", "flag", risk_level="medium", category="sw"),
        ]
        agg = aggregator.aggregate(results)
        assert agg.final_action == "block"

    def test_flag_not_escalated_when_rule_not_satisfied(self) -> None:
        """TC-PIPE-014: flag stays flag when rule is not satisfied."""
        rule = FlagEscalationRule("count >= 5")
        aggregator = ResultAggregator(flag_escalation=rule)
        results = [
            _result("a", "flag", risk_level="medium"),
            _result("b", "flag", risk_level="medium"),
        ]
        agg = aggregator.aggregate(results)
        assert agg.final_action == "flag"

    def test_no_escalation_when_no_flag_escalation_configured(self) -> None:
        """Without flag_escalation, flag stays flag."""
        aggregator = ResultAggregator()
        results = [_result("a", "flag", risk_level="high")]
        agg = aggregator.aggregate(results)
        assert agg.final_action == "flag"

    def test_escalation_not_applied_when_action_is_block(self) -> None:
        """Escalation only applies when final_action would be 'flag'."""
        rule = FlagEscalationRule("count >= 1")
        aggregator = ResultAggregator(flag_escalation=rule)
        results = [
            _result("a", "flag", risk_level="medium"),
            _result("b", "block"),
        ]
        agg = aggregator.aggregate(results)
        # block already takes precedence; escalation doesn't change anything
        assert agg.final_action == "block"

    def test_escalation_not_applied_when_action_is_modify(self) -> None:
        """Escalation only applies when final_action would be 'flag'."""
        rule = FlagEscalationRule("count >= 1")
        aggregator = ResultAggregator(flag_escalation=rule)
        results = [
            _result("a", "flag", risk_level="medium"),
            _result("b", "modify", modified_content="redacted"),
        ]
        agg = aggregator.aggregate(results)
        # modify takes precedence over flag; escalation doesn't apply
        assert agg.final_action == "modify"

    def test_escalation_not_applied_when_action_is_allow(self) -> None:
        """Escalation only applies when final_action would be 'flag'."""
        rule = FlagEscalationRule("count >= 1")
        aggregator = ResultAggregator(flag_escalation=rule)
        results = [_result("a", "allow")]
        agg = aggregator.aggregate(results)
        assert agg.final_action == "allow"
