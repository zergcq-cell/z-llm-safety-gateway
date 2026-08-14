"""Testing utilities for detector developers (DESIGN.md Section 7.4.1)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from z_llm_safety_gateway_sdk.context import DetectionContext
from z_llm_safety_gateway_sdk.result import DetectionResult


def make_context(
    *,
    direction: Literal["input", "output"] = "input",
    request_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    language: str | None = None,
    message_index: int | None = None,
) -> DetectionContext:
    """Build a test DetectionContext with sensible defaults.

    Args:
        direction: Detection direction (default ``"input"``).
        request_id: Request id; auto-generated UUID if not provided.
        user_id: Optional end-user identifier.
        metadata: Optional context metadata dict.
        language: Optional ISO 639-1 language code.
        message_index: Optional message index.

    Returns:
        A ready-to-use :class:`DetectionContext`.
    """
    return DetectionContext(
        direction=direction,
        request_id=request_id or f"req_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        metadata=metadata,
        language=language,
        message_index=message_index,
    )


def assert_allowed(result: DetectionResult) -> None:
    """Assert that a detection result is an ``allow`` with low risk."""
    assert result.action == "allow", f"expected allow, got {result.action!r}"
    assert result.risk_level in ("low", "medium"), (
        f"expected low/medium risk, got {result.risk_level!r}"
    )


def assert_blocked(result: DetectionResult) -> None:
    """Assert that a detection result is a ``block`` with high/critical risk."""
    assert result.action == "block", f"expected block, got {result.action!r}"
    assert result.risk_level in ("high", "critical"), (
        f"expected high/critical risk, got {result.risk_level!r}"
    )
    assert 0.0 <= result.confidence <= 1.0


def assert_confidence(result: DetectionResult, minimum: float = 0.5) -> None:
    """Assert that a detection result's confidence is within [minimum, 1.0]."""
    assert result.confidence >= minimum, (
        f"expected confidence >= {minimum}, got {result.confidence!r}"
    )
    assert result.confidence <= 1.0, (
        f"expected confidence <= 1.0, got {result.confidence!r}"
    )
