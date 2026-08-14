"""Modification — a content modification to apply to a message.

Constructed by the gateway pipeline engine, not by detectors.  Detectors
signal intent to modify by returning ``action="modify"`` with
``modified_content`` set on :class:`DetectionResult`.
"""

from __future__ import annotations

from typing import Any


class Modification:
    """A content modification to apply to a message."""

    __slots__ = ("detector_name", "modified_content", "priority", "message_index")

    def __init__(
        self,
        *,
        detector_name: str,
        modified_content: str,
        priority: int,
        message_index: int | None = None,
    ) -> None:
        self.detector_name = detector_name
        self.modified_content = modified_content
        self.priority = priority
        self.message_index = message_index

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        data: dict[str, Any] = {
            "detector_name": self.detector_name,
            "modified_content": self.modified_content,
            "priority": self.priority,
        }
        if self.message_index is not None:
            data["message_index"] = self.message_index
        return data

    def __repr__(self) -> str:
        return (
            f"Modification(detector_name={self.detector_name!r}, "
            f"priority={self.priority!r})"
        )
