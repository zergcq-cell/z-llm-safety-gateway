"""Detector registry for managing detector registration and lifecycle."""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

from z_llm_safety_gateway.detectors.base import Detector

logger = logging.getLogger(__name__)


def _is_detector_like(obj: Any) -> bool:
    """Structural (duck-typed) check for a Detector implementation class.

    Accepts any class exposing the Detector interface contract:
    class attributes ``name``/``category``/``description``/``version`` and
    callable (async) ``initialize``/``detect`` methods.  This deliberately
    does NOT require inheritance from the gateway's ``Detector`` base so that
    SDK-based plugins (different class hierarchy) are accepted.

    Args:
        obj: Candidate class to inspect.

    Returns:
        True when the object looks like a Detector implementation class.
    """
    if not isinstance(obj, type):
        return False
    for attr in ("name", "category", "description", "version"):
        if not hasattr(obj, attr):
            return False
    return all(
        callable(getattr(obj, method, None))
        for method in ("initialize", "detect")
    )


class DetectorRegistry:
    """Registry for managing built-in detector classes and their lifecycle.

    Maintains a name-to-class mapping. Detectors are registered at package
    initialization time and instantiated on demand via create_detector or
    initialize_all.

    v0.5.0: :meth:`register_from_entry_points` discovers third-party in-process
    plugins via the ``z_llm_safety_gateway.detectors`` entry point group
    (DESIGN.md Section 7.2.2/7.6.1).
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

    def register_from_entry_points(self, *, group: str = "z_llm_safety_gateway.detectors") -> int:
        """Discover and register third-party detectors via Python entry points.

        Loads ``importlib.metadata.entry_points(group=...)`` and registers each
        resolvable ``<module>:<ClassName>`` entry.  Existing same-name
        registrations (built-ins) are NOT overwritten.  Unresolvable entries
        are skipped with a logged warning.

        Plugins typically inherit the SDK's :class:`Detector` (from
        ``z_llm_safety_gateway_sdk``), which is a *different* class from the
        gateway's built-in ``Detector`` base.  Compatibility is therefore
        checked structurally (duck typing: class attributes + async methods),
        matching DESIGN.md Section 7.1 "Both modes share the same Detector
        interface contract".

        Args:
            group: Entry point group to scan (default
                ``z_llm_safety_gateway.detectors``).

        Returns:
            The number of plugins successfully registered.
        """
        from importlib.metadata import entry_points

        registered = 0
        for ep in entry_points(group=group):
            name = ep.name
            if name in self._detectors:
                logger.debug("entry point name already registered, skipping: %s", name)
                continue
            try:
                module_name, _, attr = ep.value.partition(":")
                module = importlib.import_module(module_name)
                detector_class = getattr(module, attr)
                if not _is_detector_like(detector_class):
                    raise TypeError(f"{ep.value} is not a Detector subclass")
                self._detectors[name] = detector_class
                registered += 1
                logger.info("registered plugin detector from entry point: %s", name)
            except Exception:
                logger.warning(
                    "failed to load entry point detector '%s' (%s)",
                    name,
                    ep.value,
                    exc_info=True,
                )
        return registered

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
        try:
            await detector.initialize(config)
        except Exception:
            shutdown = getattr(detector, "shutdown", None)
            if callable(shutdown):
                try:
                    await asyncio.wait_for(
                        shutdown(),
                        timeout=float(config.get("timeout_seconds", 5.0)),
                    )
                except Exception:
                    logger.warning(
                        "detector initialization cleanup failed: %s",
                        name,
                    )
            raise
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
