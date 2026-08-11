"""Detector abstract base class defining the detector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from z_llm_safety_gateway.models import DetectionContext, DetectionResult


class Detector(ABC):
    """Abstract base class for all content safety detectors.

    Subclasses must define the class attributes name, category, description,
    and version, and implement the async initialize and detect methods.
    """

    name: str
    category: str
    description: str
    version: str

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the detector with its configuration.

        Called once at gateway startup before any detect() calls.

        Args:
            config: Detector-specific configuration dict (thresholds, paths, etc.).
        """
        ...

    @abstractmethod
    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Run detection on the given content.

        Args:
            content: The text content to analyze.
            context: Detection context with direction, request_id, etc.

        Returns:
            A DetectionResult describing the outcome.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the detector is healthy and ready to serve.

        Returns:
            True if healthy, False otherwise. Default implementation returns True.
        """
        return True

    async def shutdown(self) -> None:  # noqa: B027
        """Release resources held by the detector.

        Called once at gateway shutdown. Default implementation is a no-op.
        """
