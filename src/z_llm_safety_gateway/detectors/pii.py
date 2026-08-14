"""PII detector: detects and redacts personally identifiable information.

Detects PII entities (email, phone, SSN, credit card, IP address) using regex
patterns compiled at initialize() time, and redacts them using a configurable
mode: ``mask``, ``replace``, or ``hash``. When PII is found the detector sets
``action='modify'`` with ``modified_content`` holding the fully redacted text.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from typing import Any

import structlog

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

# Default regex patterns for each supported PII entity type.
DEFAULT_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}

# All supported entity types in canonical detection order.
ALL_ENTITY_TYPES: list[str] = list(DEFAULT_PATTERNS.keys())

_REDACTED_PLACEHOLDER = "[REDACTED]"
_HASH_LENGTH = 16


class PIIDetector(Detector):
    """Detector for personally identifiable information (PII).

    Configuration keys (passed to ``initialize``):

    - ``redaction_mode``: ``"mask"`` | ``"replace"`` | ``"hash"`` (default ``"mask"``).
    - ``entity_types``: list of entity type names to detect (default: all).
    - ``custom_patterns``: dict of ``name -> regex`` to add or override patterns.
    """

    name: str = "pii_redaction"
    category: str = "pii"
    description: str = (
        "Detects and redacts PII: email, phone, SSN, credit card, IP address"
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._patterns: dict[str, re.Pattern[str]] = {}
        self._redaction_mode: str = "mask"
        self._entity_types: list[str] = []

    async def initialize(self, config: dict[str, Any]) -> None:
        """Compile regex patterns and store redaction configuration.

        Args:
            config: Detector configuration dict.

        Raises:
            ValueError: If a configured regex pattern is invalid.
        """
        self._redaction_mode = config.get("redaction_mode", "mask")

        # Start from defaults, then apply custom overrides/additions.
        patterns: dict[str, str] = dict(DEFAULT_PATTERNS)
        custom_patterns = config.get("custom_patterns", {})
        if isinstance(custom_patterns, dict):
            patterns.update(custom_patterns)

        # Determine which entity types to compile/detect.
        entity_types = config.get("entity_types")
        if entity_types is not None:
            self._entity_types = list(entity_types)
        else:
            self._entity_types = list(patterns.keys())

        # Compile each pattern, skipping unknown types that have no pattern.
        self._patterns = {}
        for entity_type in self._entity_types:
            pattern_str = patterns.get(entity_type)
            if pattern_str is None:
                logger.warning(
                    "PII entity type has no pattern, skipping",
                    entity_type=entity_type,
                )
                continue
            try:
                self._patterns[entity_type] = re.compile(pattern_str)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern for entity type '{entity_type}': {exc}"
                ) from exc

        logger.info(
            "PII detector initialized",
            redaction_mode=self._redaction_mode,
            entity_types=list(self._patterns.keys()),
        )

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Detect PII in content and return a redacted result.

        Args:
            content: The text content to analyze.
            context: Detection context with direction, request_id, etc.

        Returns:
            A DetectionResult. When PII is found, ``action='modify'`` with
            ``modified_content`` set to the redacted text; otherwise
            ``action='allow'``.
        """
        start = time.perf_counter()

        # Phase 1: count every entity type on the original content.
        entity_counts: dict[str, int] = {}
        for entity_type, pattern in self._patterns.items():
            matches = pattern.findall(content)
            if matches:
                entity_counts[entity_type] = len(matches)

        total_count = sum(entity_counts.values())

        # No PII found: allow without modification.
        if total_count == 0:
            duration_ms = (time.perf_counter() - start) * 1000
            return DetectionResult(
                detector_name=self.name,
                category=self.category,
                action="allow",
                confidence=0.0,
                risk_level="low",
                message="No PII detected",
                details={"entities": {}, "total_count": 0},
                duration_ms=duration_ms,
            )

        # Phase 2: progressively redact each entity type in the content.
        modified_content = content
        for entity_type, pattern in self._patterns.items():
            if entity_type not in entity_counts:
                continue
            modified_content = pattern.sub(
                self._make_replacer(entity_type), modified_content
            )

        duration_ms = (time.perf_counter() - start) * 1000
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="modify",
            confidence=1.0,
            risk_level="medium",
            message=f"Detected {total_count} PII entity/entities",
            details={"entities": entity_counts, "total_count": total_count},
            modified_content=modified_content,
            duration_ms=duration_ms,
        )

    def _make_replacer(self, entity_type: str) -> Callable[[re.Match[str]], str]:
        """Build a regex substitution callable for the given entity type.

        Closing over ``entity_type`` explicitly avoids the loop-variable capture
        pitfall while keeping a fully typed replacement function for mypy.
        """

        def _replace(match: re.Match[str]) -> str:
            return self._redact(entity_type, match.group())

        return _replace

    def _redact(self, entity_type: str, value: str) -> str:
        """Return the redacted form of a PII value based on the active mode."""
        if self._redaction_mode == "replace":
            return _REDACTED_PLACEHOLDER
        if self._redaction_mode == "hash":
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            return digest[:_HASH_LENGTH]
        return self._mask_value(entity_type, value)

    def _mask_value(self, entity_type: str, value: str) -> str:
        """Mask a PII value, preserving minimal structure for recognition."""
        if entity_type == "email":
            return self._mask_email(value)
        if len(value) <= 2:
            return _REDACTED_PLACEHOLDER
        # Keep first and last char, replace the middle portion.
        return value[0] + "***" + value[-1]

    def _mask_email(self, email: str) -> str:
        """Mask an email as ``<first>***@<first>***.<tld>``.

        Preserves the first character of the local part and domain name plus
        the full TLD, so the structure remains recognizable without exposing
        the original value.
        """
        local, sep, domain = email.partition("@")
        if not sep:
            return _REDACTED_PLACEHOLDER
        masked_local = (local[0] + "***") if local else "***"
        if "." in domain:
            domain_name, _, tld = domain.rpartition(".")
            masked_domain = (domain_name[0] + "***") if domain_name else "***"
            return f"{masked_local}@{masked_domain}.{tld}"
        return f"{masked_local}@***"
