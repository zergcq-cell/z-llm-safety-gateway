"""Unit tests for FlagEscalationRule DSL — TC-PIPE-013/014/015.

Covers the flag-escalation DSL parser and evaluator as specified in
design.md Decision 7 and DESIGN.md Section 5.6.

Tests cover:
- Variable-based comparisons (count, max_risk_level)
- All comparison operators (>=, >, <=, <, ==, !=)
- categories contains syntax
- and / or logical operators (left-to-right evaluation)
- Invalid syntax → ValueError
- FlagEscalationRule.evaluate() with real DetectionResult objects
"""

from __future__ import annotations

import pytest

from z_llm_safety_gateway.models import DetectionResult
from z_llm_safety_gateway.pipeline.flag_escalation import (
    RISK_LEVEL_MAP,
    FlagEscalationRule,
    parse,
)

# --------------------------------------------------------------------------- #
# Helper: create a flag DetectionResult
# --------------------------------------------------------------------------- #


def _flag_result(
    category: str = "prompt_injection",
    risk_level: str = "medium",
) -> DetectionResult:
    """Create a DetectionResult with action='flag' for testing."""
    return DetectionResult(
        detector_name="test_detector",
        category=category,
        action="flag",
        confidence=0.6,
        risk_level=risk_level,
        message="flag result",
    )


# --------------------------------------------------------------------------- #
# parse() — variable comparisons
# --------------------------------------------------------------------------- #


class TestParseCountComparisons:
    """DSL: count variable with various operators."""

    @pytest.mark.parametrize(
        ("rule", "count", "expected"),
        [
            ("count >= 3", 3, True),
            ("count >= 3", 2, False),
            ("count > 2", 3, True),
            ("count > 2", 2, False),
            ("count <= 5", 5, True),
            ("count <= 5", 6, False),
            ("count < 4", 3, True),
            ("count < 4", 4, False),
            ("count == 3", 3, True),
            ("count == 3", 2, False),
            ("count != 0", 1, True),
            ("count != 0", 0, False),
        ],
    )
    def test_count_comparison(
        self, rule: str, count: int, expected: bool
    ) -> None:
        """Parametrized: count comparisons with all operators."""
        evaluator = parse(rule)
        ctx = {"count": count, "max_risk_level": 0, "categories": []}
        assert evaluator(ctx) is expected


class TestParseMaxRiskLevelComparisons:
    """DSL: max_risk_level variable with risk-level names."""

    @pytest.mark.parametrize(
        ("rule", "max_risk", "expected"),
        [
            ("max_risk_level >= medium", 1, True),  # medium=1
            ("max_risk_level >= medium", 0, False),  # low=0
            ("max_risk_level >= high", 2, True),  # high=2
            ("max_risk_level >= high", 1, False),
            ("max_risk_level > low", 1, True),
            ("max_risk_level > low", 0, False),
            ("max_risk_level <= medium", 1, True),
            ("max_risk_level <= medium", 2, False),
            ("max_risk_level < critical", 2, True),  # critical=3
            ("max_risk_level < critical", 3, False),
            ("max_risk_level == high", 2, True),
            ("max_risk_level == high", 1, False),
            ("max_risk_level != low", 1, True),
            ("max_risk_level != low", 0, False),
        ],
    )
    def test_max_risk_level_comparison(
        self, rule: str, max_risk: int, expected: bool
    ) -> None:
        """Parametrized: max_risk_level comparisons with risk-level names."""
        evaluator = parse(rule)
        ctx = {"count": 0, "max_risk_level": max_risk, "categories": []}
        assert evaluator(ctx) is expected

    def test_max_risk_level_with_numeric_value(self) -> None:
        """max_risk_level can also be compared with numeric values."""
        evaluator = parse("max_risk_level >= 2")
        assert evaluator({"count": 0, "max_risk_level": 2, "categories": []}) is True
        assert evaluator({"count": 0, "max_risk_level": 1, "categories": []}) is False


# --------------------------------------------------------------------------- #
# parse() — categories contains
# --------------------------------------------------------------------------- #


class TestParseCategoriesContains:
    """DSL: categories contains <value>."""

    def test_categories_contains_present(self) -> None:
        """categories contains returns True when the category is present."""
        evaluator = parse("categories contains prompt_injection")
        ctx = {"count": 1, "max_risk_level": 0, "categories": ["prompt_injection"]}
        assert evaluator(ctx) is True

    def test_categories_contains_absent(self) -> None:
        """categories contains returns False when the category is absent."""
        evaluator = parse("categories contains prompt_injection")
        ctx = {"count": 1, "max_risk_level": 0, "categories": ["pii"]}
        assert evaluator(ctx) is False

    def test_categories_contains_empty_list(self) -> None:
        """categories contains returns False for an empty list."""
        evaluator = parse("categories contains pii")
        ctx = {"count": 0, "max_risk_level": 0, "categories": []}
        assert evaluator(ctx) is False

    def test_categories_contains_multiple(self) -> None:
        """categories contains works with multiple categories in the list."""
        evaluator = parse("categories contains toxicity")
        ctx = {
            "count": 3,
            "max_risk_level": 2,
            "categories": ["prompt_injection", "pii", "toxicity"],
        }
        assert evaluator(ctx) is True


# --------------------------------------------------------------------------- #
# parse() — logical operators (and, or)
# --------------------------------------------------------------------------- #


class TestParseLogicalOperators:
    """DSL: and / or operators (left-to-right evaluation)."""

    def test_and_both_true(self) -> None:
        """'a and b' returns True when both are True."""
        evaluator = parse("count >= 3 and max_risk_level >= medium")
        ctx = {"count": 3, "max_risk_level": 1, "categories": []}
        assert evaluator(ctx) is True

    def test_and_first_false(self) -> None:
        """'a and b' returns False when first is False."""
        evaluator = parse("count >= 3 and max_risk_level >= medium")
        ctx = {"count": 2, "max_risk_level": 1, "categories": []}
        assert evaluator(ctx) is False

    def test_and_second_false(self) -> None:
        """'a and b' returns False when second is False."""
        evaluator = parse("count >= 3 and max_risk_level >= medium")
        ctx = {"count": 3, "max_risk_level": 0, "categories": []}
        assert evaluator(ctx) is False

    def test_or_both_false(self) -> None:
        """'a or b' returns False when both are False."""
        evaluator = parse("count >= 5 or max_risk_level >= high")
        ctx = {"count": 1, "max_risk_level": 0, "categories": []}
        assert evaluator(ctx) is False

    def test_or_first_true(self) -> None:
        """'a or b' returns True when first is True."""
        evaluator = parse("count >= 5 or max_risk_level >= high")
        ctx = {"count": 5, "max_risk_level": 0, "categories": []}
        assert evaluator(ctx) is True

    def test_or_second_true(self) -> None:
        """'a or b' returns True when second is True."""
        evaluator = parse("count >= 5 or max_risk_level >= high")
        ctx = {"count": 1, "max_risk_level": 2, "categories": []}
        assert evaluator(ctx) is True

    def test_and_or_left_to_right(self) -> None:
        """Left-to-right evaluation: 'a or b and c' = '(a or b) and c'."""
        # Standard precedence would be 'a or (b and c)' = True or ... = True
        # Left-to-right gives '(a or b) and c' = True and False = False
        evaluator = parse("count >= 5 or max_risk_level >= high and count < 1")
        # Left-to-right: (count>=5=True) or (max_risk>=high=True) → True
        # Then: True and (count<1=False) → False
        ctx = {"count": 5, "max_risk_level": 2, "categories": []}
        assert evaluator(ctx) is False

    def test_three_comparisons_with_and(self) -> None:
        """Three comparisons joined by 'and'."""
        evaluator = parse(
            "count >= 2 and max_risk_level >= medium and categories contains pii"
        )
        ctx = {"count": 2, "max_risk_level": 1, "categories": ["pii"]}
        assert evaluator(ctx) is True

    def test_categories_contains_with_and(self) -> None:
        """categories contains combined with count via 'and'."""
        evaluator = parse("count >= 2 and categories contains prompt_injection")
        ctx = {"count": 2, "max_risk_level": 0, "categories": ["prompt_injection"]}
        assert evaluator(ctx) is True

    def test_categories_contains_with_or(self) -> None:
        """categories contains combined with count via 'or'."""
        evaluator = parse("count >= 5 or categories contains prompt_injection")
        ctx = {"count": 1, "max_risk_level": 0, "categories": ["prompt_injection"]}
        assert evaluator(ctx) is True


# --------------------------------------------------------------------------- #
# parse() — invalid syntax
# --------------------------------------------------------------------------- #


class TestParseInvalidSyntax:
    """DSL: invalid syntax raises ValueError."""

    @pytest.mark.parametrize(
        "rule",
        [
            "",  # empty
            "   ",  # whitespace only
            "count",  # missing operator and value
            "count >=",  # missing value
            "count >= ",  # missing value (trailing space)
            "count >> 3",  # invalid operator
            "count = 3",  # invalid operator (single =)
            "unknown_var >= 3",  # unknown variable
            "count >= 3 and",  # trailing logic op
            "count >= 3 or",  # trailing logic op
            "count >= 3 and or count >= 2",  # double logic op
            "count >= 3 extra",  # trailing token
            "and count >= 3",  # leading logic op
            "categories",  # incomplete categories
            "categories contains",  # missing value after contains
            "categories >= 3",  # wrong operator for categories
            "count contains 3",  # contains on wrong variable
            "count >= 3 @xyz",  # invalid character
        ],
    )
    def test_invalid_syntax_raises_value_error(self, rule: str) -> None:
        """Parametrized: invalid DSL strings raise ValueError."""
        with pytest.raises(ValueError):
            parse(rule)


# --------------------------------------------------------------------------- #
# FlagEscalationRule.evaluate()
# --------------------------------------------------------------------------- #


class TestFlagEscalationRuleEvaluate:
    """FlagEscalationRule.evaluate() with real DetectionResult objects."""

    def test_evaluate_true_when_rule_satisfied(self) -> None:
        """TC-PIPE-013: Rule evaluates to True when conditions are met."""
        rule = FlagEscalationRule("count >= 3 and max_risk_level >= medium")
        flags = [
            _flag_result("prompt_injection", "medium"),
            _flag_result("pii", "low"),
            _flag_result("toxicity", "medium"),
        ]
        assert rule.evaluate(flags) is True

    def test_evaluate_false_when_count_too_low(self) -> None:
        """Rule returns False when count is below threshold."""
        rule = FlagEscalationRule("count >= 3 and max_risk_level >= medium")
        flags = [
            _flag_result("prompt_injection", "medium"),
            _flag_result("pii", "low"),
        ]
        assert rule.evaluate(flags) is False

    def test_evaluate_false_when_risk_too_low(self) -> None:
        """Rule returns False when max_risk_level is below threshold."""
        rule = FlagEscalationRule("count >= 3 and max_risk_level >= high")
        flags = [
            _flag_result("prompt_injection", "medium"),
            _flag_result("pii", "medium"),
            _flag_result("toxicity", "medium"),
        ]
        assert rule.evaluate(flags) is False

    def test_evaluate_with_empty_flag_list(self) -> None:
        """Rule returns False when there are no flag results."""
        rule = FlagEscalationRule("count >= 3")
        assert rule.evaluate([]) is False

    def test_evaluate_categories_contains(self) -> None:
        """Rule with categories contains evaluates correctly."""
        rule = FlagEscalationRule("categories contains prompt_injection")
        flags = [_flag_result("pii", "medium")]
        assert rule.evaluate(flags) is False

        flags = [_flag_result("prompt_injection", "medium")]
        assert rule.evaluate(flags) is True

    def test_evaluate_or_logic(self) -> None:
        """Rule with 'or' evaluates correctly."""
        rule = FlagEscalationRule("count >= 5 or max_risk_level >= high")
        flags = [_flag_result("prompt_injection", "high")]
        assert rule.evaluate(flags) is True

    def test_rule_str_property(self) -> None:
        """The rule_str property returns the original rule string."""
        rule = FlagEscalationRule("count >= 3")
        assert rule.rule_str == "count >= 3"

    def test_constructor_raises_on_invalid_syntax(self) -> None:
        """TC-PIPE-015: Invalid rule syntax raises ValueError at construction."""
        with pytest.raises(ValueError):
            FlagEscalationRule("invalid rule @@@@")

    def test_risk_level_map_values(self) -> None:
        """RISK_LEVEL_MAP has correct numeric mappings."""
        assert RISK_LEVEL_MAP == {"low": 0, "medium": 1, "high": 2, "critical": 3}

    def test_evaluate_with_critical_risk(self) -> None:
        """Critical risk level (3) satisfies >= high and >= critical."""
        rule = FlagEscalationRule("max_risk_level >= critical")
        flags = [_flag_result("toxicity", "critical")]
        assert rule.evaluate(flags) is True

    def test_evaluate_multiple_categories(self) -> None:
        """Categories list contains all flag result categories."""
        rule = FlagEscalationRule("count >= 2 and categories contains pii")
        flags = [
            _flag_result("prompt_injection", "medium"),
            _flag_result("pii", "low"),
        ]
        assert rule.evaluate(flags) is True
