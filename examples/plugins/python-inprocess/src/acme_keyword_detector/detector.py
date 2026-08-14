"""AcmeKeywordDetector — example in-process detector.

Demonstrates the recommended way to build an in-process plugin for the
z LLM Safety Gateway:

1. Inherit ``z_llm_safety_gateway_sdk.Detector``.
2. Set class attributes ``name``/``category``/``description``/``version``.
3. Implement ``initialize()`` and ``detect()``.
4. Register via the ``z_llm_safety_gateway.detectors`` entry point group
   (see pyproject.toml).  The gateway auto-discovers it at startup.

The detector blocks content containing configured disallowed keywords, and
modifies content when ``redact_keywords`` is enabled.
"""

from __future__ import annotations

from z_llm_safety_gateway_sdk import DetectionContext, DetectionResult, Detector


class AcmeKeywordDetector(Detector):
    """Blocks or redacts configured keywords (acme corporate policy demo)."""

    name = "acme_keyword"
    category = "custom"
    description = "Acme corporate keyword policy detector (example plugin)"
    version = "1.0.0"

    async def initialize(self, config: dict) -> None:
        """Load configuration from the gateway's detector config block."""
        self.block_keywords: list[str] = config.get("block_keywords", [])
        self.redact_keywords: list[str] = config.get("redact_keywords", [])
        self.block_threshold: float = config.get("block_threshold", 0.8)

    async def detect(self, content: str, context: DetectionContext) -> DetectionResult:
        """Run keyword policy detection on *content*.

        Returns:
            ``block`` when a block keyword is found (confidence = threshold),
            ``modify`` when a redact keyword is found, ``allow`` otherwise.
        """
        lowered = content.lower()

        for keyword in self.block_keywords:
            if keyword.lower() in lowered:
                return DetectionResult(
                    detector_name=self.name,
                    category=self.category,
                    action="block",
                    confidence=self.block_threshold,
                    risk_level="high",
                    message=f"Blocked keyword '{keyword}' detected",
                    details={"matched_keyword": keyword},
                )

        for keyword in self.redact_keywords:
            if keyword.lower() in lowered:
                modified = content.replace(keyword, "*" * len(keyword))
                return DetectionResult(
                    detector_name=self.name,
                    category=self.category,
                    action="modify",
                    confidence=0.9,
                    risk_level="medium",
                    message=f"Redacted keyword '{keyword}'",
                    details={"matched_keyword": keyword},
                    modified_content=modified,
                )

        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="No policy violation",
        )
