"""Content extraction from OpenAI-format chat messages."""

from __future__ import annotations

from typing import Any

from z_llm_safety_gateway.models import ExtractedContent

# Roles that represent potential input attack surfaces.
EXTRACTABLE_ROLES = {"user", "system", "developer"}


def extract_content(messages: list[dict[str, Any]]) -> list[ExtractedContent]:
    """Extract text content from chat messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        List of ExtractedContent for each user/system/developer message.
    """
    result: list[ExtractedContent] = []

    for index, message in enumerate(messages):
        role = message.get("role", "")
        if role not in EXTRACTABLE_ROLES:
            continue

        content = message.get("content")
        text = _extract_text_from_content(content)
        if text is None:
            continue

        result.append(
            ExtractedContent(
                message_index=index,
                role=role,
                text=text,
            )
        )

    return result


def _extract_text_from_content(content: Any) -> str | None:
    """Extract text from a message content field.

    Args:
        content: Either a string or a list of content parts (multimodal).

    Returns:
        Extracted text string, or None if no text content found.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        if text_parts:
            return "\n".join(text_parts)

    return None
