"""Unit tests for the find_result_by_action utility (v0.4.0 fix).

Ensures that block/flag/modify event metadata references the detector that
actually triggered the action, not just the first detector in the list
(which may have returned ``allow``).
"""

from __future__ import annotations

from z_llm_safety_gateway.models import DetectionResult, find_result_by_action


def _make_result(
    name: str, action: str, category: str = "test", confidence: float = 0.9
) -> DetectionResult:
    """Build a minimal DetectionResult for testing."""
    return DetectionResult(
        detector_name=name,
        category=category,
        action=action,  # type: ignore[arg-type]
        confidence=confidence,
        risk_level="high",  # type: ignore[arg-type]
        message=f"{name} triggered {action}",
    )


def test_find_block_result_returns_matching() -> None:
    """When multiple detectors ran, the one with action='block' is returned."""
    results = [
        _make_result("safe-detector", "allow"),
        _make_result("block-detector", "block"),
        _make_result("flag-detector", "flag"),
    ]
    found = find_result_by_action(results, "block")
    assert found is not None
    assert found.detector_name == "block-detector"


def test_find_block_result_none_when_no_match() -> None:
    """Returns None when no result matches the given action."""
    results = [_make_result("det1", "allow"), _make_result("det2", "flag")]
    assert find_result_by_action(results, "block") is None


def test_find_result_with_action_set() -> None:
    """Accepts a set of actions and returns the first match."""
    results = [
        _make_result("det1", "allow"),
        _make_result("det2", "modify"),
    ]
    found = find_result_by_action(results, {"flag", "modify"})
    assert found is not None
    assert found.detector_name == "det2"


def test_find_result_empty_list_returns_none() -> None:
    """Returns None for an empty results list."""
    assert find_result_by_action([], "block") is None


def test_find_result_first_match_wins() -> None:
    """When multiple results match, the first one is returned."""
    results = [
        _make_result("first-block", "block", confidence=0.8),
        _make_result("second-block", "block", confidence=0.95),
    ]
    found = find_result_by_action(results, "block")
    assert found is not None
    assert found.detector_name == "first-block"
