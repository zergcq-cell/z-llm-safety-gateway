"""Flag escalation rule DSL — parse-time compilation, request-time evaluation.

Implements a simple expression parser for flag-to-block escalation rules as
specified in DESIGN.md Section 5.6 and design.md Decision 7.

Supported DSL syntax::

    <variable> <operator> <value> [and|or <variable> <operator> <value>]*

Variables:
    - ``count`` — number of flag results (int)
    - ``max_risk_level`` — highest risk level among flag results (int: low=0,
      medium=1, high=2, critical=3)
    - ``categories`` — list of flag result category strings

Operators:
    - ``>=``, ``>``, ``<=``, ``<``, ``==``, ``!=``

Special syntax:
    - ``categories contains <value>`` — membership test

Logic:
    - ``and``, ``or`` — evaluated left-to-right (no parentheses, no precedence)

The rule string is parsed at config-load time into a callable. Invalid syntax
raises :class:`ValueError`.
"""

from __future__ import annotations

import operator as _operator
import re
from collections.abc import Callable
from typing import Any

from z_llm_safety_gateway.models import DetectionResult

# Risk-level to numeric mapping (low < medium < high < critical).
RISK_LEVEL_MAP: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Regex patterns for tokenization.
_OP_RE = re.compile(r">=|<=|==|!=|>|<")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_IDENT_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

# Valid variables for comparison (categories has its own syntax).
_VARIABLES = frozenset({"count", "max_risk_level"})
_OPERATORS = frozenset({">=", ">", "<=", "<", "==", "!="})
_LOGIC_OPS = frozenset({"and", "or"})

# Operator string → comparison function.
_CMP_FUNCS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": _operator.ge,
    ">": _operator.gt,
    "<=": _operator.le,
    "<": _operator.lt,
    "==": _operator.eq,
    "!=": _operator.ne,
}


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #


def _tokenize(rule_str: str) -> list[str]:
    """Split *rule_str* into a list of token strings.

    Raises:
        ValueError: If an unexpected character is encountered.
    """
    tokens: list[str] = []
    pos = 0
    length = len(rule_str)

    while pos < length:
        char = rule_str[pos]

        # Skip whitespace
        if char.isspace():
            pos += 1
            continue

        # Try two-char and one-char operators
        m = _OP_RE.match(rule_str, pos)
        if m:
            tokens.append(m.group())
            pos = m.end()
            continue

        # Try numbers
        m = _NUMBER_RE.match(rule_str, pos)
        if m:
            tokens.append(m.group())
            pos = m.end()
            continue

        # Try identifiers / keywords
        m = _IDENT_RE.match(rule_str, pos)
        if m:
            tokens.append(m.group())
            pos = m.end()
            continue

        raise ValueError(
            f"Invalid character '{char}' at position {pos} in rule: '{rule_str}'"
        )

    return tokens


def _parse_value(token: str) -> int | float | str:
    """Parse a value token into its Python equivalent.

    Numbers become ``int`` or ``float``. Risk-level names become their numeric
    mapping. Everything else is treated as a literal string (category name).
    """
    # Try integer
    if token.isdigit():
        return int(token)

    # Try float
    try:
        return float(token)
    except ValueError:
        pass

    # Risk level name
    if token in RISK_LEVEL_MAP:
        return RISK_LEVEL_MAP[token]

    # Category identifier
    return token


# --------------------------------------------------------------------------- #
# Comparison parser
# --------------------------------------------------------------------------- #

# Type alias for an evaluator function that takes a context dict and returns bool.
Evaluator = Callable[[dict[str, Any]], bool]


def _parse_comparison(
    tokens: list[str], pos: int
) -> tuple[Evaluator, int]:
    """Parse a single comparison starting at *tokens[pos]*.

    Returns the evaluator callable and the position after the consumed tokens.

    Raises:
        ValueError: If the tokens do not form a valid comparison.
    """
    if pos >= len(tokens):
        raise ValueError("Unexpected end of rule: expected a comparison")

    var = tokens[pos]

    # Special case: categories contains <value>
    if var == "categories":
        if pos + 1 >= len(tokens):
            raise ValueError("Expected 'contains' after 'categories'")
        if tokens[pos + 1] != "contains":
            raise ValueError(
                f"Expected 'contains' after 'categories', got '{tokens[pos + 1]}'"
            )
        if pos + 2 >= len(tokens):
            raise ValueError("Expected a value after 'contains'")
        expected_category = tokens[pos + 2]

        def _eval_contains(ctx: dict[str, Any]) -> bool:
            return expected_category in ctx["categories"]

        return _eval_contains, pos + 3

    # Regular comparison: var op value
    if var not in _VARIABLES:
        raise ValueError(
            f"Unknown variable '{var}'; expected one of: count, max_risk_level, categories"
        )

    if pos + 1 >= len(tokens):
        raise ValueError(f"Expected an operator after '{var}'")

    operator = tokens[pos + 1]
    if operator not in _OPERATORS:
        raise ValueError(
            f"Invalid operator '{operator}'; expected one of: >=, >, <=, <, ==, !="
        )

    if pos + 2 >= len(tokens):
        raise ValueError(f"Expected a value after '{operator}'")

    raw_value = tokens[pos + 2]
    value = _parse_value(raw_value)

    # Map operator string to the corresponding comparison function.
    _cmp_fn = _CMP_FUNCS[operator]

    def _eval_comparison(ctx: dict[str, Any]) -> bool:
        actual: Any = ctx[var]
        return bool(_cmp_fn(actual, value))

    return _eval_comparison, pos + 3


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse(rule_str: str) -> Evaluator:
    """Parse a flag-escalation rule string into an evaluation function.

    The returned callable accepts a context ``dict`` with keys ``count``
    (int), ``max_risk_level`` (int 0-3), and ``categories`` (list[str]),
    and returns ``True`` if the rule is satisfied.

    Args:
        rule_str: The DSL expression to parse.

    Returns:
        A callable ``ctx -> bool``.

    Raises:
        ValueError: If *rule_str* is empty or contains invalid syntax.
    """
    rule_str = rule_str.strip()
    if not rule_str:
        raise ValueError("Rule string is empty")

    tokens = _tokenize(rule_str)
    if not tokens:
        raise ValueError("Rule string contains no tokens")

    # Parse the first comparison.
    first_eval, pos = _parse_comparison(tokens, 0)

    # Parse remaining (logic_op comparison)* pairs.
    parts: list[tuple[str, Evaluator]] = [("", first_eval)]

    while pos < len(tokens):
        logic_op = tokens[pos]
        if logic_op not in _LOGIC_OPS:
            raise ValueError(
                f"Expected 'and' or 'or' at position {pos}, got '{logic_op}'"
            )
        pos += 1
        next_eval, pos = _parse_comparison(tokens, pos)
        parts.append((logic_op, next_eval))

    # Build the left-to-right evaluator.
    def evaluate(ctx: dict[str, Any]) -> bool:
        result = parts[0][1](ctx)
        for op, eval_fn in parts[1:]:
            result = (result and eval_fn(ctx)) if op == "and" else (result or eval_fn(ctx))
        return bool(result)

    return evaluate


class FlagEscalationRule:
    """A compiled flag-escalation rule.

    The rule string is parsed at construction time (config-load). At request
    time, :meth:`evaluate` builds the evaluation context from the accumulated
    flag results and returns whether the flags should be escalated to a block.

    Args:
        rule_str: The DSL expression (e.g. ``"count >= 3 and max_risk_level >= medium"``).

    Raises:
        ValueError: If *rule_str* is not valid DSL.
    """

    def __init__(self, rule_str: str) -> None:
        self._rule_str = rule_str
        self._evaluator: Evaluator = parse(rule_str)

    @property
    def rule_str(self) -> str:
        """The original rule string."""
        return self._rule_str

    def evaluate(self, flag_results: list[DetectionResult]) -> bool:
        """Evaluate the rule against a list of flag DetectionResults.

        Args:
            flag_results: Detection results whose action is ``"flag"``.

        Returns:
            ``True`` if the rule is satisfied (flags should escalate to block).
        """
        ctx: dict[str, Any] = {
            "count": len(flag_results),
            "max_risk_level": max(
                (RISK_LEVEL_MAP.get(r.risk_level, 0) for r in flag_results),
                default=0,
            ),
            "categories": [r.category for r in flag_results],
        }
        return self._evaluator(ctx)
