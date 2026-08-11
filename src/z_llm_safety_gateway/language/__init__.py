"""Language detection — langdetect wrapper for ISO 639-1 code extraction."""

from __future__ import annotations

from z_llm_safety_gateway.language.detector import (
    detect_language,
    detect_language_for_messages,
)

__all__ = ["detect_language", "detect_language_for_messages"]
