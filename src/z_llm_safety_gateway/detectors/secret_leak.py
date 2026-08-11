"""Secret leak detector: detects leaked API keys, AWS credentials, private keys, and JWTs."""

from __future__ import annotations

import re
from typing import Any

import structlog

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

# Default secret regex patterns.
# Each entry maps a secret type name to a regex string.
DEFAULT_PATTERNS: dict[str, str] = {
    "api_key": r"sk-[a-zA-Z0-9]{20,}",
    "aws_secret": (
        r"(?:AKIA[0-9A-Z]{16}"
        r"|aws_secret_access_key['\"\s:=]+[A-Za-z0-9/+=]{40})"
    ),
    "private_key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "jwt_token": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
}

DEFAULT_PATTERN_NAMES: list[str] = [
    "api_key",
    "aws_secret",
    "private_key",
    "jwt_token",
]


class SecretLeakDetector(Detector):
    """Detector that scans content for leaked secrets and credentials.

    Supports detection of:
      - OpenAI-style API keys (``sk-...``)
      - AWS access key IDs (``AKIA...``) and secret access keys
      - PEM private key headers (``-----BEGIN ... PRIVATE KEY-----``)
      - JWT tokens (``header.payload.signature``)

    Custom patterns can be added or default patterns overridden via the
    ``custom_patterns`` config option.
    """

    name: str = "secret_leak"
    category: str = "secret_leak"
    description: str = (
        "Detects leaked secrets and credentials: API keys, AWS keys, "
        "private keys, and JWT tokens."
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}

    async def initialize(self, config: dict[str, Any]) -> None:
        """Compile regex patterns based on configuration.

        Args:
            config: Optional keys:
                - ``patterns``: list of pattern names to activate.
                  Defaults to all default patterns.
                - ``custom_patterns``: dict of name -> regex string to add
                  or override defaults.

        Raises:
            ValueError: If any regex pattern is invalid.
        """
        # Start with a copy of default patterns
        effective: dict[str, str] = dict(DEFAULT_PATTERNS)

        # Apply custom pattern overrides / additions
        custom_patterns = config.get("custom_patterns", {})
        if custom_patterns:
            effective.update(custom_patterns)

        # Filter to only the requested pattern names
        patterns_list = config.get("patterns")
        if patterns_list is not None:
            effective = {
                name: pat for name, pat in effective.items() if name in patterns_list
            }

        # Compile all patterns, raising on invalid regex
        compiled: dict[str, re.Pattern[str]] = {}
        for name, pattern_str in effective.items():
            try:
                compiled[name] = re.compile(pattern_str)
            except re.error as exc:
                raise ValueError(
                    f"Invalid regex pattern for '{name}': {exc}"
                ) from exc

        self._compiled_patterns = compiled
        logger.info(
            "SecretLeakDetector initialized",
            active_patterns=list(compiled.keys()),
        )

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Scan content for secrets using all active compiled patterns.

        Args:
            content: The text content to analyze.
            context: Detection context (direction, request_id, etc.).

        Returns:
            DetectionResult with action='block' if any secret is found,
            otherwise action='allow'. The details dict contains per-type
            match counts and a total, with no raw secret values.
        """
        secrets: dict[str, int] = {}

        for name, pattern in self._compiled_patterns.items():
            matches = pattern.findall(content)
            if matches:
                secrets[name] = len(matches)

        total_count = sum(secrets.values())

        if total_count > 0:
            types_str = ", ".join(sorted(secrets.keys()))
            message = (
                f"Detected {total_count} potential secret(s) of type(s): {types_str}"
            )
            return DetectionResult(
                detector_name=self.name,
                category=self.category,
                action="block",
                confidence=1.0,
                risk_level="critical",
                message=message,
                details={"secrets": secrets, "total_count": total_count},
            )

        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="No secrets detected",
            details={"secrets": {}, "total_count": 0},
        )
