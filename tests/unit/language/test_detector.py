"""Unit tests for language detection — TC-LD-001 through TC-LD-008.

Covers the ``detect_language`` and ``detect_language_for_messages`` functions
that wrap the ``langdetect`` library, as specified in ``spec.yaml`` (capability
``language-detection``) and ``design.md`` Decision / Architecture.

``langdetect`` is non-deterministic by default; ``DetectorFactory.seed = 0`` is
set at import time of the detector module to make results reproducible.  Test
texts are intentionally long to keep ``langdetect`` stable on short input.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langdetect import LangDetectException

from z_llm_safety_gateway.language import detect_language, detect_language_for_messages
from z_llm_safety_gateway.models import ExtractedContent

# Patch target for ``detect`` as imported into the detector module.
_DETECT_TARGET = "z_llm_safety_gateway.language.detector.detect"

# Sufficiently long, natural-language samples for stable detection.
_EN_TEXT = (
    "The quick brown fox jumps over the lazy dog. "
    "Language detection works best on longer passages of natural text. "
    "This sentence is included to provide enough signal for the detector."
)
_ZH_TEXT = (
    "你好，今天天气怎么样？我想去公园散步，你觉得呢？"
    "语言检测需要足够长的文本才能稳定工作，所以这里多写一些中文内容。"
)
_JA_TEXT = (
    "こんにちは、お元気ですか？今日はとても良い天気ですね。"
    "言語検出は長いテキストの方が安定して動作しますので、少し長めに書いています。"
)


# ---------------------------------------------------------------------------
# TC-LD-001: English text detection
# ---------------------------------------------------------------------------


def test_detect_language_english() -> None:
    """TC-LD-001: English text is detected as ``"en"``.

    GIVEN a sufficiently long English text
    WHEN detect_language(text) is called
    THEN the result SHALL be ``"en"``
    """
    result = detect_language(_EN_TEXT)

    assert result == "en"


# ---------------------------------------------------------------------------
# TC-LD-002: Chinese text detection
# ---------------------------------------------------------------------------


def test_detect_language_chinese() -> None:
    """TC-LD-002: Chinese text is detected as ``"zh"`` (or ``"zh-cn"``).

    GIVEN a sufficiently long Chinese text
    WHEN detect_language(text) is called
    THEN the result SHALL be ``"zh"`` or ``"zh-cn"``
    """
    result = detect_language(_ZH_TEXT)

    assert result in ("zh", "zh-cn")


# ---------------------------------------------------------------------------
# TC-LD-003: Japanese text detection
# ---------------------------------------------------------------------------


def test_detect_language_japanese() -> None:
    """TC-LD-003: Japanese text is detected as ``"ja"``.

    GIVEN a sufficiently long Japanese text
    WHEN detect_language(text) is called
    THEN the result SHALL be ``"ja"``
    """
    result = detect_language(_JA_TEXT)

    assert result == "ja"


# ---------------------------------------------------------------------------
# TC-LD-004: Empty text returns None
# ---------------------------------------------------------------------------


def test_detect_language_empty_text() -> None:
    """TC-LD-004: Empty text returns ``None`` without raising.

    GIVEN an empty string content=""
    WHEN detect_language(content) is called
    THEN the result SHALL be ``None``
    AND no exception SHALL be raised
    """
    result = detect_language("")

    assert result is None


# ---------------------------------------------------------------------------
# TC-LD-005: Whitespace-only text returns None
# ---------------------------------------------------------------------------


def test_detect_language_whitespace_text() -> None:
    """TC-LD-005: Whitespace-only text returns ``None`` without raising.

    GIVEN a whitespace-only string content="   \\n\\t  "
    WHEN detect_language(content) is called
    THEN the result SHALL be ``None``
    AND no exception SHALL be raised
    """
    result = detect_language("   \n\t  ")

    assert result is None


# ---------------------------------------------------------------------------
# TC-LD-006: langdetect exception returns None
# ---------------------------------------------------------------------------


def test_detect_language_handles_langdetect_exception() -> None:
    """TC-LD-006: A ``LangDetectException`` is swallowed and ``None`` returned.

    GIVEN langdetect.detect() raises LangDetectException (e.g. no features)
    WHEN detect_language(content) is called
    THEN the exception SHALL be caught
    AND the result SHALL be ``None``
    AND no exception SHALL propagate to the caller
    """
    with patch(_DETECT_TARGET, side_effect=LangDetectException(0, "No features in text.")):
        result = detect_language("12345")

    assert result is None


# ---------------------------------------------------------------------------
# TC-LD-007: detect_language_for_messages returns first non-None language
# ---------------------------------------------------------------------------


def test_detect_language_for_messages_returns_first_non_none() -> None:
    """TC-LD-007: The first non-``None`` detection wins as the primary language.

    GIVEN a list of three ExtractedContent messages:
      message 0: empty text       → None
      message 1: English text     → "en"
      message 2: Chinese text     → "zh"
    WHEN detect_language_for_messages(contents) is called
    THEN the result SHALL be ``"en"`` (first non-None)
    """
    contents = [
        ExtractedContent(message_index=0, role="system", text=""),
        ExtractedContent(message_index=1, role="user", text=_EN_TEXT),
        ExtractedContent(message_index=2, role="user", text=_ZH_TEXT),
    ]

    result = detect_language_for_messages(contents)

    assert result == "en"


# ---------------------------------------------------------------------------
# TC-LD-008: detect_language_for_messages with all-empty returns None
# ---------------------------------------------------------------------------


def test_detect_language_for_messages_all_empty_returns_none() -> None:
    """TC-LD-008: When every message yields ``None``, the aggregate is ``None``.

    GIVEN a list of ExtractedContent messages all with empty/whitespace text
    WHEN detect_language_for_messages(contents) is called
    THEN the result SHALL be ``None``
    """
    contents = [
        ExtractedContent(message_index=0, role="system", text=""),
        ExtractedContent(message_index=1, role="user", text="   "),
        ExtractedContent(message_index=2, role="assistant", text="\n\t"),
    ]

    result = detect_language_for_messages(contents)

    assert result is None


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_detect_language_for_messages_empty_list_returns_none() -> None:
    """An empty message list yields ``None`` as the primary language."""

    result = detect_language_for_messages([])

    assert result is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\t  \r\n",
    ],
)
def test_detect_language_blank_variants_return_none(text: str) -> None:
    """Parametrized: any blank/whitespace-only string yields ``None``."""

    result = detect_language(text)

    assert result is None
