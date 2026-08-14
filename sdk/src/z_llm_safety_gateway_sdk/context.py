"""DetectionContext — context information passed to detectors."""

from __future__ import annotations

from typing import Any, Literal


class DetectionContext:
    """Context information passed to a detector for each detection call.

    Attributes:
        direction: ``"input"`` (request content) or ``"output"`` (response).
        request_id: Unique request identifier.
        user_id: Optional end-user identifier.
        metadata: Arbitrary key/value context (e.g. model name, provider).
        language: Optional ISO 639-1 language code of the content.
        message_index: For input direction, the message index in the request.
    """

    __slots__ = (
        "direction",
        "request_id",
        "user_id",
        "metadata",
        "language",
        "message_index",
    )

    def __init__(
        self,
        *,
        direction: Literal["input", "output"],
        request_id: str,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        language: str | None = None,
        message_index: int | None = None,
    ) -> None:
        self.direction = direction
        self.request_id = request_id
        self.user_id = user_id
        self.metadata: dict[str, Any] = metadata if metadata is not None else {}
        self.language = language
        self.message_index = message_index

    def __repr__(self) -> str:
        return (
            f"DetectionContext(direction={self.direction!r}, "
            f"request_id={self.request_id!r}, language={self.language!r})"
        )
