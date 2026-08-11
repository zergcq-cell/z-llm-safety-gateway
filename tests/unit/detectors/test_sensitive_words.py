"""Tests for SensitiveWordsDetector — Aho-Corasick based sensitive word detection.

Covers REQ-001 through REQ-008 (TC-SW-001 to TC-SW-016) from the
sensitive-words-detector spec.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ahocorasick
import pytest

from z_llm_safety_gateway.detectors.sensitive_words import SensitiveWordsDetector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"
EN_FIXTURE = str(FIXTURES_DIR / "sensitive_en.txt")
ZH_FIXTURE = str(FIXTURES_DIR / "sensitive_zh.txt")


def _ctx(
    language: str | None = None,
    request_id: str = "req-test",
) -> DetectionContext:
    """Helper to build a DetectionContext."""
    return DetectionContext(
        direction="input",
        request_id=request_id,
        language=language,
    )


class TestAhoCorasickMatching:
    """REQ-001: Aho-Corasick multi-pattern matching."""

    async def test_tc_sw_001_multi_pattern_matching(self) -> None:
        """TC-SW-001: Aho-Corasick matches multiple patterns in a single pass."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam", "scam", "fraud"]}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("This is a spam and scam message", ctx)

        assert result.category == "sensitive_words"
        assert result.details["match_count"] == 2
        assert "spam" in result.details["matched_words"]
        assert "scam" in result.details["matched_words"]
        assert "fraud" not in result.details["matched_words"]

    async def test_tc_sw_006_initialize_builds_ahocorasick_automaton(self) -> None:
        """TC-SW-006: initialize() builds automaton using pyahocorasick."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam", "scam"]}
        await detector.initialize(config)

        automaton = detector._automata["en"]
        assert isinstance(automaton, ahocorasick.Automaton)
        assert len(automaton) == 2


class TestMultiLanguageWordLists:
    """REQ-002: Multi-language word list selection via context.language."""

    async def test_tc_sw_002_chinese_word_list_matching(self) -> None:
        """TC-SW-002: context.language='zh' uses the Chinese word list."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {
            "word_list_file": EN_FIXTURE,
            "word_list_file_zh": ZH_FIXTURE,
        }
        await detector.initialize(config)

        ctx = _ctx(language="zh")
        result = await detector.detect("这是一个 赌博 网站", ctx)

        assert result.details["match_count"] >= 1
        assert "赌博" in result.details["matched_words"]
        assert result.details["language"] == "zh"

    async def test_tc_sw_007_english_word_list_selection(self) -> None:
        """TC-SW-007: context.language='en' uses the English word list."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {
            "word_list_file": EN_FIXTURE,
            "word_list_file_zh": ZH_FIXTURE,
        }
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("This is spam", ctx)

        assert result.details["match_count"] == 1
        assert "spam" in result.details["matched_words"]
        assert result.details["language"] == "en"

    async def test_tc_sw_014_language_none_falls_back_to_english(self) -> None:
        """TC-SW-014: context.language=None falls back to English word list."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {
            "word_list_file": EN_FIXTURE,
            "word_list_file_zh": ZH_FIXTURE,
        }
        await detector.initialize(config)

        ctx = _ctx(language=None)
        result = await detector.detect("This is spam", ctx)

        assert result.details["match_count"] == 1
        assert "spam" in result.details["matched_words"]
        assert result.details["language"] == "en"

    async def test_tc_sw_015_only_english_list_language_zh_returns_allow(self) -> None:
        """TC-SW-015: Only English word list, language='zh' returns allow."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"word_list_file": EN_FIXTURE}
        await detector.initialize(config)

        ctx = _ctx(language="zh")
        result = await detector.detect("这是一个 赌博 网站", ctx)

        assert result.action == "allow"
        assert result.details["match_count"] == 0


class TestMatchModes:
    """REQ-003: Match modes (exact, fuzzy)."""

    async def test_tc_sw_003_exact_mode_no_substring_match(self) -> None:
        """TC-SW-003: exact mode does not match 'spam' within 'spamming'."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam"], "match_mode": "exact"}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("This is spamming", ctx)

        assert result.details["match_count"] == 0
        assert result.action == "allow"

    async def test_tc_sw_004_fuzzy_mode_substring_match(self) -> None:
        """TC-SW-004: fuzzy mode matches 'spam' within 'spamming'."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam"], "match_mode": "fuzzy"}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("This is spamming", ctx)

        assert result.details["match_count"] == 1
        assert "spam" in result.details["matched_words"]

    async def test_tc_sw_008_exact_mode_whole_word_match(self) -> None:
        """TC-SW-008: exact mode matches 'spam' as a whole word."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam"], "match_mode": "exact"}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("This is spam", ctx)

        assert result.details["match_count"] == 1
        assert "spam" in result.details["matched_words"]


class TestWordListFileLoading:
    """REQ-004: Load word lists from files."""

    async def test_tc_sw_009_load_from_file_skips_comments_and_empty_lines(self) -> None:
        """TC-SW-009: Load from file, skip empty lines and comment lines."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"word_list_file": EN_FIXTURE}
        await detector.initialize(config)

        automaton = detector._automata["en"]
        # Fixture has 6 actual words (spam, scam, fraud, abuse, hack, exploit)
        # and 3 comment lines + 2 empty lines that should be skipped.
        assert len(automaton) == 6

        ctx = _ctx(language="en")
        result = await detector.detect("spam scam fraud abuse hack exploit", ctx)

        assert result.details["match_count"] == 6

    async def test_tc_sw_016_word_list_file_missing_raises_error(self) -> None:
        """TC-SW-016: Missing word list file raises error with file path."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"word_list_file": "nonexistent.txt"}

        with pytest.raises(Exception, match="nonexistent.txt"):
            await detector.initialize(config)


class TestAutomatonCompilation:
    """REQ-005: Compile automaton in initialize()."""

    async def test_tc_sw_010_initialize_compiles_and_stores_automaton(self) -> None:
        """TC-SW-010: Automaton is compiled in initialize() and reused in detect()."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam", "scam"]}
        await detector.initialize(config)

        automaton_before = detector._automata["en"]

        ctx = _ctx(language="en")
        await detector.detect("spam", ctx)
        await detector.detect("scam", ctx)

        automaton_after = detector._automata["en"]
        assert automaton_before is automaton_after


class TestThresholdDecisions:
    """REQ-006: Action decisions based on match count and thresholds."""

    async def test_tc_sw_005_block_threshold_3_plus_matches(self) -> None:
        """TC-SW-005: 3+ matches with block_threshold=3 → block."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {
            "words": ["spam", "scam", "fraud"],
            "block_threshold": 3,
            "flag_threshold": 1,
        }
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("spam scam fraud", ctx)

        assert result.action == "block"
        assert result.confidence == 1.0
        assert result.risk_level == "high"
        assert result.details["match_count"] == 3

    async def test_tc_sw_011_flag_threshold_1_to_2_matches(self) -> None:
        """TC-SW-011: 1-2 matches with flag_threshold=1 → flag."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {
            "words": ["spam", "scam"],
            "block_threshold": 3,
            "flag_threshold": 1,
        }
        await detector.initialize(config)

        ctx = _ctx(language="en")

        # 1 match → flag
        result1 = await detector.detect("spam", ctx)
        assert result1.action == "flag"
        assert result1.confidence == 0.5
        assert result1.risk_level == "medium"
        assert result1.details["match_count"] == 1

        # 2 matches → flag
        result2 = await detector.detect("spam scam", ctx)
        assert result2.action == "flag"
        assert result2.confidence == 0.5
        assert result2.risk_level == "medium"
        assert result2.details["match_count"] == 2

    async def test_tc_sw_012_zero_matches_returns_allow(self) -> None:
        """TC-SW-012: 0 matches → allow."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam"]}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("Hello world", ctx)

        assert result.action == "allow"
        assert result.confidence == 0.0
        assert result.risk_level == "low"
        assert result.details["match_count"] == 0


class TestDetailsRecording:
    """REQ-007: details records matched words, count, language."""

    async def test_tc_sw_013_details_records_matched_words_count_language(self) -> None:
        """TC-SW-013: details contains matched_words, match_count, language."""
        detector = SensitiveWordsDetector()
        config: dict[str, Any] = {"words": ["spam", "scam"]}
        await detector.initialize(config)

        ctx = _ctx(language="en")
        result = await detector.detect("spam spam scam", ctx)

        assert isinstance(result, DetectionResult)
        assert result.details["matched_words"] == ["spam", "spam", "scam"]
        assert result.details["match_count"] == 3
        assert result.details["language"] == "en"
