"""Prompt injection detector using regex pattern matching.

Detects common prompt injection attacks (e.g., "ignore previous instructions",
DAN jailbreak, system prompt extraction) using precompiled regex patterns.
Supports both English and Chinese injection patterns.

The detector only computes a confidence score based on matched patterns and
their severity levels. The final action (block / flag / allow) is determined
by the pipeline engine's ThresholdDecisionEngine using per-detector thresholds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

import structlog

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

# Severity level to confidence-score mapping.
# high=0.5 ensures that 3+ high-severity matches produce confidence >= 0.85
# (3 * 0.5 = 1.5, capped at 1.0, which is >= 0.85).
SEVERITY_SCORES: dict[str, float] = {
    "high": 0.5,
    "medium": 0.3,
    "low": 0.15,
}


@dataclass(frozen=True)
class InjectionPattern:
    """Definition of a single injection detection pattern.

    Attributes:
        name: Human-readable identifier for the pattern.
        pattern: Regex pattern string to compile and search for.
        severity: Severity level ("high", "medium", or "low").
    """

    name: str
    pattern: str
    severity: str


# --- Default English injection patterns --- #

_DEFAULT_ENGLISH_PATTERNS: list[InjectionPattern] = [
    InjectionPattern("ignore previous instructions", r"ignore previous instructions", "high"),
    InjectionPattern("system prompt:", r"system prompt:", "high"),
    InjectionPattern("you are now", r"you are now", "high"),
    InjectionPattern("DAN", r"DAN", "high"),
    InjectionPattern("do anything now", r"do anything now", "high"),
    InjectionPattern("ignore the above", r"ignore the above", "high"),
    InjectionPattern("jailbreak", r"jailbreak", "high"),
    InjectionPattern("pretend you are", r"pretend you are", "high"),
    InjectionPattern("forget your rules", r"forget your rules", "high"),
    InjectionPattern("reveal your prompt", r"reveal your prompt", "high"),
    InjectionPattern("show me your prompt", r"show me your prompt", "high"),
    InjectionPattern("new instructions", r"new instructions", "medium"),
    InjectionPattern("override", r"override", "medium"),
    InjectionPattern("act as", r"act as", "medium"),
]

# --- Default Chinese injection patterns --- #

_DEFAULT_CHINESE_PATTERNS: list[InjectionPattern] = [
    InjectionPattern("忽略之前的指令", r"忽略之前的指令", "high"),
    InjectionPattern("你现在是", r"你现在是", "high"),
    InjectionPattern("系统提示", r"系统提示", "high"),
    InjectionPattern("忽略以上", r"忽略以上", "high"),
    InjectionPattern("忽略上面的", r"忽略上面的", "high"),
    InjectionPattern("越狱", r"越狱", "high"),
    InjectionPattern("假装你是", r"假装你是", "high"),
    InjectionPattern("忘记你的规则", r"忘记你的规则", "high"),
    InjectionPattern("显示你的提示", r"显示你的提示", "high"),
    InjectionPattern("角色扮演", r"角色扮演", "medium"),
    InjectionPattern("新的指令", r"新的指令", "medium"),
    InjectionPattern("覆盖", r"覆盖", "medium"),
    InjectionPattern("扮演", r"扮演", "low"),
]

# Combined default patterns (English + Chinese).
DEFAULT_PATTERNS: list[InjectionPattern] = [
    *_DEFAULT_ENGLISH_PATTERNS,
    *_DEFAULT_CHINESE_PATTERNS,
]


class PromptInjectionDetector(Detector):
    """Detector for prompt injection attacks using regex pattern matching.

    Compiles injection patterns during ``initialize()`` and searches input
    content against all compiled patterns during ``detect()``. The confidence
    score is calculated as the sum of severity scores for all matched patterns,
    capped at 1.0.

    The detector returns a placeholder ``action="allow"``; the pipeline engine
    overrides the action using :class:`ThresholdDecisionEngine` based on the
    confidence score and configured thresholds.
    """

    name: str = "prompt_injection"
    category: str = "prompt_injection"
    description: str = (
        "Detects prompt injection attacks using regex pattern matching "
        "with support for English and Chinese patterns"
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._compiled_patterns: list[tuple[InjectionPattern, re.Pattern[str]]] = []

    async def initialize(self, config: dict[str, Any]) -> None:
        """Compile injection patterns from config or defaults.

        If ``config`` contains a ``"patterns"`` key, those patterns are used
        instead of the defaults. Each pattern must be a dict with ``"name"``,
        ``"pattern"``, and ``"severity"`` keys.

        Args:
            config: Detector configuration dict. May contain a ``"patterns"``
                key with a list of pattern definitions.

        Raises:
            ValueError: If a pattern has an invalid regex, missing keys, or
                an unrecognized severity level.
        """
        patterns_data = config.get("patterns")

        if patterns_data is not None:
            if not isinstance(patterns_data, list):
                raise ValueError("'patterns' in config must be a list")
            injection_patterns = self._parse_patterns(patterns_data)
        else:
            injection_patterns = list(DEFAULT_PATTERNS)

        compiled: list[tuple[InjectionPattern, re.Pattern[str]]] = []
        for ip in injection_patterns:
            try:
                regex = re.compile(ip.pattern, re.IGNORECASE)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern '{ip.pattern}' "
                    f"for pattern '{ip.name}': {exc}"
                ) from exc
            compiled.append((ip, regex))

        self._compiled_patterns = compiled
        logger.info(
            "prompt_injection_detector_initialized",
            pattern_count=len(compiled),
        )

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Run prompt injection detection on the given content.

        Searches the content against all compiled patterns and calculates a
        confidence score based on the severity of matched patterns.

        Args:
            content: The text content to analyze.
            context: Detection context with direction, request_id, etc.

        Returns:
            A DetectionResult with the computed confidence, matched patterns
            in details, and a placeholder action (the pipeline engine
            determines the final action via thresholds).
        """
        matched_patterns: list[dict[str, str]] = []
        total_score = 0.0

        for ip, regex in self._compiled_patterns:
            if regex.search(content):
                matched_patterns.append(
                    {"name": ip.name, "severity": ip.severity}
                )
                total_score += SEVERITY_SCORES[ip.severity]

        confidence = min(total_score, 1.0)
        risk_level = self._compute_risk_level(confidence)

        if matched_patterns:
            message = (
                f"Detected {len(matched_patterns)} "
                f"prompt injection pattern(s)"
            )
        else:
            message = "No prompt injection patterns detected"

        logger.debug(
            "prompt_injection_detection_complete",
            confidence=confidence,
            matched_count=len(matched_patterns),
            risk_level=risk_level,
        )

        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",  # Placeholder — pipeline engine overrides via thresholds
            confidence=confidence,
            risk_level=risk_level,
            message=message,
            details={"matched_patterns": matched_patterns},
        )

    @staticmethod
    def _compute_risk_level(confidence: float) -> Literal["low", "medium", "high", "critical"]:
        """Map a confidence score to a risk level.

        Args:
            confidence: Confidence score in [0.0, 1.0].

        Returns:
            One of "low", "medium", "high", or "critical".
        """
        if confidence >= 0.85:
            return "high"
        if confidence >= 0.50:
            return "medium"
        return "low"

    @staticmethod
    def _parse_patterns(patterns_data: list[Any]) -> list[InjectionPattern]:
        """Parse pattern definitions from config into InjectionPattern objects.

        Args:
            patterns_data: List of pattern dicts from config.

        Returns:
            List of InjectionPattern objects.

        Raises:
            ValueError: If a pattern dict is missing required keys or has
                an invalid severity.
        """
        result: list[InjectionPattern] = []
        for p in patterns_data:
            if not isinstance(p, dict):
                raise ValueError(f"Pattern must be a dict, got {type(p).__name__}")
            if "name" not in p or "pattern" not in p or "severity" not in p:
                raise ValueError(
                    "Pattern must have 'name', 'pattern', and 'severity' keys"
                )
            name = str(p["name"])
            pattern = str(p["pattern"])
            severity = str(p["severity"])
            if severity not in SEVERITY_SCORES:
                raise ValueError(
                    f"Invalid severity '{severity}' for pattern '{name}'. "
                    f"Must be one of: {', '.join(SEVERITY_SCORES.keys())}"
                )
            result.append(InjectionPattern(name=name, pattern=pattern, severity=severity))
        return result
