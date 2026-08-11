"""Language detection — langdetect wrapper for ISO 639-1 code extraction.

Provides deterministic language detection built on top of the ``langdetect``
library.  ``DetectorFactory.seed`` is pinned at import time so that repeated
detections of the same text always yield the same result.

The module exposes two public functions:

- :func:`detect_language` — detect the language of a single text string.
- :func:`detect_language_for_messages` — detect the *primary* language across
  a list of extracted chat messages (first non-``None`` result wins).

Both functions never raise: empty/blank text and ``LangDetectException``
failures are gracefully mapped to ``None`` so that language detection never
blocks request processing.
"""

from __future__ import annotations

from typing import cast

import langdetect
import structlog
from langdetect import DetectorFactory, LangDetectException, detect

from z_llm_safety_gateway.models import ExtractedContent

# Pin the random seed so detection results are deterministic across runs.
DetectorFactory.seed = 0

# Silence langdetect's internal logging to avoid noise in production logs.
# Some langdetect versions expose a module-level ``logger`` object; others
# rely solely on the verbose flag of the Detector (which defaults to False).
# Guard the access so the code works regardless of the installed version.
_langdetect_logger = getattr(langdetect, "logger", None)
if _langdetect_logger is not None:
    _langdetect_logger.disabled = True

logger = structlog.get_logger(__name__)


def detect_language(text: str) -> str | None:
    """Detect the language of ``text`` and return an ISO 639-1 code.

    Args:
        text: The input text to analyse.

    Returns:
        A lowercase two-letter ISO 639-1 language code (e.g. ``"en"``,
        ``"zh"``, ``"ja"``), or ``None`` when the text is empty/blank or
        ``langdetect`` cannot determine the language.

    This function never raises: any ``LangDetectException`` is caught and
    logged at ``warning`` level, then ``None`` is returned so that callers
    (notably the request pipeline) are never blocked by a detection failure.
    """
    if not text or not text.strip():
        return None

    try:
        return cast(str, detect(text))
    except LangDetectException as exc:
        logger.warning(
            "language_detection_failed",
            text_length=len(text),
            error=str(exc),
        )
        return None


def detect_language_for_messages(
    contents: list[ExtractedContent],
) -> str | None:
    """Detect the primary language across a list of extracted messages.

    Each message is analysed independently via :func:`detect_language`.  The
    first non-``None`` result is returned as the *primary* language of the
    request.  If every message yields ``None`` (or the list is empty),
    ``None`` is returned.

    Args:
        contents: Extracted content items from chat messages, in order.

    Returns:
        The ISO 639-1 code of the first message whose language could be
        determined, or ``None`` if none could be detected.
    """
    for content in contents:
        language = detect_language(content.text)
        if language is not None:
            return language
    return None
