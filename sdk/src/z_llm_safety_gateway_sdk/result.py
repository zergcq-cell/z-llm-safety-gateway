"""DetectionResult — result returned by a detector after analyzing content."""

from __future__ import annotations

from typing import Any, Literal


class DetectionResult:
    """Result returned by a detector after analyzing content.

    Attributes:
        detector_name: Name of the detector producing this result.
        category: Detection category (e.g. ``"toxicity"``, ``"pii"``).
        action: One of ``"allow"``, ``"block"``, ``"flag"``, ``"modify"``.
        confidence: Confidence in the result, in ``[0.0, 1.0]``.
        risk_level: One of ``"low"``, ``"medium"``, ``"high"``, ``"critical"``.
        message: Human-readable description of the result.
        details: Detector-specific details (arbitrary JSON-serializable dict).
        modified_content: Only set when ``action == "modify"``.
    """

    __slots__ = (
        "detector_name",
        "category",
        "action",
        "confidence",
        "risk_level",
        "message",
        "details",
        "modified_content",
    )

    def __init__(
        self,
        *,
        detector_name: str,
        category: str,
        action: Literal["allow", "block", "flag", "modify"],
        confidence: float,
        risk_level: Literal["low", "medium", "high", "critical"],
        message: str,
        details: dict[str, Any] | None = None,
        modified_content: str | None = None,
    ) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {confidence}")
        self.detector_name = detector_name
        self.category = category
        self.action = action
        self.confidence = confidence
        self.risk_level = risk_level
        self.message = message
        self.details: dict[str, Any] = details if details is not None else {}
        self.modified_content = modified_content

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        data: dict[str, Any] = {
            "detector_name": self.detector_name,
            "category": self.category,
            "action": self.action,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "message": self.message,
            "details": self.details,
        }
        if self.modified_content is not None:
            data["modified_content"] = self.modified_content
        return data

    def __repr__(self) -> str:
        return (
            f"DetectionResult(detector_name={self.detector_name!r}, "
            f"action={self.action!r}, confidence={self.confidence!r}, "
            f"risk_level={self.risk_level!r})"
        )
