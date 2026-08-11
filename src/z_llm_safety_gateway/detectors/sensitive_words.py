"""Sensitive words detector using Aho-Corasick automaton.

Implements multi-pattern matching with O(n) complexity where n is the
content length, independent of the word list size. Supports multi-language
word lists (English / Chinese), exact and fuzzy match modes, and
count-based threshold decisions.

Spec: sensitive-words-detector/spec.yaml (REQ-001 to REQ-008).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import ahocorasick
import structlog

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

_DEFAULT_MATCH_MODE = "exact"
_DEFAULT_BLOCK_THRESHOLD = 3
_DEFAULT_FLAG_THRESHOLD = 1


class SensitiveWordsDetector(Detector):
    """Aho-Corasick based sensitive word detector.

    Builds separate compiled automata for English and Chinese word lists
    during ``initialize()``. The ``detect()`` method selects the automaton
    based on ``context.language`` and performs multi-pattern matching in
    a single pass over the content.

    Match modes:

    - ``exact`` (default): Only whole-word matches are counted. For Latin
      text, a match must be bounded by non-alphanumeric characters. For
      CJK text, a match must not be adjacent to other CJK characters.
    - ``fuzzy``: Any substring match counts, no word-boundary check.

    Confidence / action mapping (count-based):

    - ``match_count >= block_threshold`` → confidence 1.0, action ``block``
    - ``match_count >= flag_threshold``  → confidence 0.5, action ``flag``
    - otherwise                         → confidence 0.0, action ``allow``
    """

    name: str = "sensitive_words"
    category: str = "sensitive_words"
    description: str = "Aho-Corasick based sensitive word detection"
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._automata: dict[str, Any] = {}
        self._match_mode: str = _DEFAULT_MATCH_MODE
        self._block_threshold: int = _DEFAULT_BLOCK_THRESHOLD
        self._flag_threshold: int = _DEFAULT_FLAG_THRESHOLD

    async def initialize(self, config: dict[str, Any]) -> None:
        """Build and compile Aho-Corasick automata from config.

        Args:
            config: May contain ``word_list_file`` (English file path),
                ``word_list_file_zh`` (Chinese file path), ``words``
                (inline English word list), ``match_mode``
                (``"exact"`` or ``"fuzzy"``), ``block_threshold`` (int),
                and ``flag_threshold`` (int).

        Raises:
            FileNotFoundError: If a configured word list file does not exist.
        """
        self._match_mode = config.get("match_mode", _DEFAULT_MATCH_MODE)
        self._block_threshold = config.get(
            "block_threshold", _DEFAULT_BLOCK_THRESHOLD
        )
        self._flag_threshold = config.get(
            "flag_threshold", _DEFAULT_FLAG_THRESHOLD
        )

        # English words: file takes precedence over inline list.
        word_list_file = config.get("word_list_file")
        if word_list_file:
            en_words = self._load_word_list(str(word_list_file))
        else:
            en_words = list(config.get("words", []))

        # Chinese words: file only (no inline option per spec).
        word_list_file_zh = config.get("word_list_file_zh")
        zh_words = (
            self._load_word_list(str(word_list_file_zh))
            if word_list_file_zh
            else []
        )

        self._automata = {
            "en": self._build_automaton(en_words),
            "zh": self._build_automaton(zh_words),
        }

        logger.info(
            "sensitive_words_initialized",
            en_word_count=len(en_words),
            zh_word_count=len(zh_words),
            match_mode=self._match_mode,
            block_threshold=self._block_threshold,
            flag_threshold=self._flag_threshold,
        )

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Run sensitive word detection on the given content.

        Args:
            content: The text to analyze.
            context: Detection context; ``context.language`` selects the
                word list (``"en"`` or ``"zh"``). Falls back to English.

        Returns:
            A DetectionResult with matched words, count, and language in
            details.
        """
        language = self._select_language(context.language)
        automaton = self._automata.get(language)

        # Empty or missing automaton → no matches possible.
        if automaton is None or len(automaton) == 0:
            return self._build_result([], language)

        matched_words: list[str] = []
        for end_index, word in automaton.iter(content):
            if self._match_mode == "exact" and not self._is_whole_word(
                content, end_index, str(word), language
            ):
                continue
            matched_words.append(str(word))

        return self._build_result(matched_words, language)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _select_language(self, language: str | None) -> str:
        """Determine the effective language for word list selection.

        Falls back to English if the language is None or not recognized.
        """
        if language is not None and language in self._automata:
            return language
        return "en"

    @staticmethod
    def _load_word_list(file_path: str) -> list[str]:
        """Load words from a file, skipping comments and empty lines.

        Args:
            file_path: Path to the word list file.

        Returns:
            List of words loaded from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Word list file not found: {file_path}")

        words: list[str] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                words.append(stripped)
        return words

    @staticmethod
    def _build_automaton(words: list[str]) -> Any:
        """Build and compile an Aho-Corasick automaton from a word list.

        If the word list is empty, an uncompiled (empty) automaton is
        returned — ``make_automaton()`` raises on an empty trie.
        """
        automaton = ahocorasick.Automaton()
        for word in words:
            if word:
                automaton.add_word(word, word)
        if len(automaton) > 0:
            automaton.make_automaton()
        return automaton

    @staticmethod
    def _is_whole_word(
        content: str,
        end_index: int,
        word: str,
        language: str,
    ) -> bool:
        """Check whether a match is a whole word (not a substring).

        For Latin text (``language != "zh"``): the characters immediately
        before and after the match must not be alphanumeric.

        For CJK text (``language == "zh"``): the characters immediately
        before and after the match must not be CJK ideographs.
        """
        start = end_index - len(word) + 1

        if language == "zh":
            if start > 0 and _is_cjk(content[start - 1]):
                return False
            if end_index < len(content) - 1 and _is_cjk(content[end_index + 1]):
                return False
        else:
            if start > 0 and content[start - 1].isalnum():
                return False
            if end_index < len(content) - 1 and content[end_index + 1].isalnum():
                return False

        return True

    def _build_result(
        self,
        matched_words: list[str],
        language: str,
    ) -> DetectionResult:
        """Build a DetectionResult from the matched words and language."""
        match_count = len(matched_words)

        action: Literal["allow", "block", "flag"]
        risk_level: Literal["low", "medium", "high"]
        confidence: float

        if match_count >= self._block_threshold:
            action = "block"
            risk_level = "high"
            confidence = 1.0
        elif match_count >= self._flag_threshold:
            action = "flag"
            risk_level = "medium"
            confidence = 0.5
        else:
            action = "allow"
            risk_level = "low"
            confidence = 0.0

        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action=action,
            confidence=confidence,
            risk_level=risk_level,
            message=f"Found {match_count} sensitive word(s)",
            details={
                "matched_words": matched_words,
                "match_count": match_count,
                "language": language,
            },
        )


def _is_cjk(char: str) -> bool:
    """Check if a character is a CJK Unified Ideograph."""
    code_point = ord(char)
    return (
        0x4E00 <= code_point <= 0x9FFF  # CJK Unified Ideographs
        or 0x3400 <= code_point <= 0x4DBF  # CJK Extension A
    )
