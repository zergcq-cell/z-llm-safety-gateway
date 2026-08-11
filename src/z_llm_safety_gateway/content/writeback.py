"""Writeback modifications to original request messages."""

from __future__ import annotations

import copy
from typing import Any

from z_llm_safety_gateway.models import Modification


def apply_modifications(
    request: dict[str, Any], modifications: list[Modification]
) -> dict[str, Any]:
    """Apply content modifications to a request.

    Args:
        request: The original request dict containing 'messages'.
        modifications: List of modifications to apply, sorted by priority.

    Returns:
        Modified request dict (deep copy, original is not mutated).
    """
    if not modifications:
        return copy.deepcopy(request)

    result = copy.deepcopy(request)
    messages = result.get("messages", [])

    sorted_modifications = sorted(modifications, key=lambda m: m.priority)

    for mod in sorted_modifications:
        if mod.message_index < 0 or mod.message_index >= len(messages):
            continue
        message = messages[mod.message_index]
        _apply_modification_to_message(message, mod)

    return result


def _apply_modification_to_message(
    message: dict[str, Any], mod: Modification
) -> None:
    """Apply a single modification to a message in-place.

    Args:
        message: The message dict to modify.
        mod: The modification to apply.
    """
    content = message.get("content")

    if isinstance(content, str):
        message["content"] = mod.modified_content
        return

    if isinstance(content, list):
        first_text_found = False
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                if not first_text_found:
                    part["text"] = mod.modified_content
                    first_text_found = True
                else:
                    part["text"] = ""
