"""Unit tests for SlidingWindow.

Covers TC-SSE-003 and TC-SSE-004 (sse-streaming spec).
"""

from __future__ import annotations

from z_llm_safety_gateway.streaming.sliding_window import SlidingWindow


# --------------------------------------------------------------------------- #
# TC-SSE-003: character accumulation + window triggering + slide
# --------------------------------------------------------------------------- #
def test_window_accumulates_and_triggers_at_window_size():
    """TC-SSE-003: buffer accumulates until window_size, then triggers."""
    window = SlidingWindow(window_size=10, overlap=3)
    assert window.is_ready() is False

    window.append("abcdefghij")  # 10 chars = window_size
    assert window.is_ready() is True


def test_window_slides_retaining_overlap():
    """TC-SSE-003b: after consume, trailing overlap chars are retained."""
    window = SlidingWindow(window_size=10, overlap=3)
    window.append("abcdefghij")
    content, retained = window.consume_window()
    assert content == "abcdefghij"
    # Slide forward by window_size - overlap = 7, retain last 3 (hij)
    assert retained == "hij"


def test_window_accumulates_across_multiple_appends():
    """TC-SSE-003c: appends accumulate across chunks without early trigger."""
    window = SlidingWindow(window_size=10, overlap=3)
    window.append("abc")
    window.append("defg")
    assert window.is_ready() is False  # 7 chars
    window.append("hij")  # 10 chars
    assert window.is_ready() is True


# --------------------------------------------------------------------------- #
# TC-SSE-004: overlap preserves cross-boundary content
# --------------------------------------------------------------------------- #
def test_overlap_preserves_boundary_content():
    """TC-SSE-004: cross-boundary content is present in the next window."""
    window = SlidingWindow(window_size=10, overlap=3)
    # First window content "abcdefghij" — boundary keyword spans end
    window.append("abcdefghij")
    _, retained = window.consume_window()
    assert retained == "hij"

    # Next window starts with the retained overlap + new content
    window.append("klmno")  # "hijklmno" = 8 chars, needs 2 more
    assert retained + "klmno" == "hijklmno"
    # The boundary content "hij" is retained so the next detection sees it
    window.append("pq")
    content, _ = window.consume_window()
    assert content == "hijklmnopq"


# --------------------------------------------------------------------------- #
# Boundary: empty append / below window
# --------------------------------------------------------------------------- #
def test_window_below_size_no_trigger():
    """TC-SSE-003d: content shorter than window_size does not trigger."""
    window = SlidingWindow(window_size=200, overlap=50)
    window.append("short text")
    assert window.is_ready() is False


def test_window_consume_when_not_ready_returns_empty():
    """TC-SSE-003e: consume_window when not ready returns empty content."""
    window = SlidingWindow(window_size=10, overlap=3)
    window.append("abc")
    content, retained = window.consume_window()
    assert content == ""
    assert retained == "abc"
