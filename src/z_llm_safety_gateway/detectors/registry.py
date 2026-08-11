"""Detector registry for managing detector registration and lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from z_llm_safety_gateway.detectors.base import Detector

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Registry for managing built-in detector classes and their lifecycle.

    Maintains a name-to-class mapping. Detectors are registered at package
    initialization time and instantiated on demand via create_detector or
    initialize_all.
    """

    def __init__(self) -> None:
        self._detectors: dict[str, type[Detector]] = {}

    def register(self, name: str, detector_class: type[Detector]) -> None:
        """Register a detector class under the given name.

        Args:
            name: Unique detector name used for lookup.
            detector_class: The Detector subclass to register.
        """
        self._detectors[name] = detector_class

    def get(self, name: str) -> type[Detector]:
        """Look up a registered detector class by name.

        Args:
            name: The registered detector name.

        Returns:
            The Detector subclass registered under that name.

        Raises:
            KeyError: If no detector is registered under the given name.
        """
        if name not in self._detectors:
            raise KeyError(f"Detector '{name}' is not registered")
        return self._detectors[name]

    def list(self) -> list[str]:
        """Return a list of all registered detector names.

        Returns:
            List of registered detector name strings.
        """
        return list(self._detectors.keys())

    async def create_detector(
        self, name: str, config: dict[str, Any]
    ) -> Detector:
        """Instantiate and initialize a detector by name.

        Args:
            name: The registered detector name.
            config: Configuration dict passed to the detector's initialize().

        Returns:
            An initialized Detector instance.

        Raises:
            KeyError: If no detector is registered under the given name.
        """
        detector_class = self.get(name)
        detector = detector_class()
        await detector.initialize(config)
        return detector

    async def initialize_all(
        self, detectors_config: dict[str, dict[str, Any]]
    ) -> dict[str, Detector]:
        """Create and initialize all configured detectors.

        Detectors that fail to initialize are skipped and logged.

        Args:
            detectors_config: Mapping of detector name to its config dict.

        Returns:
            Mapping of successfully initialized detector name to instance.
        """
        detectors: dict[str, Detector] = {}
        for name, config in detectors_config.items():
            try:
                detector = await self.create_detector(name, config)
                detectors[name] = detector
            except Exception:
                logger.exception("Failed to initialize detector: %s", name)
        return detectors

    @staticmethod
    async def shutdown_all(detectors: dict[str, Detector]) -> None:
        """Shut down all detectors, catching exceptions per detector.

        Args:
            detectors: Mapping of detector name to instance to shut down.
        """
        for name, detector in detectors.items():
            try:
                await detector.shutdown()
            except Exception:
                logger.exception("Failed to shut down detector: %s", name)
