"""Pydantic models for content extraction and modification."""

from __future__ import annotations

from pydantic import BaseModel


class ExtractedContent(BaseModel):
    """Extracted text content from a chat message."""

    message_index: int
    role: str
    text: str


class Modification(BaseModel):
    """A content modification to apply to a message."""

    detector_name: str
    modified_content: str
    priority: int
    message_index: int
