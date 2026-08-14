"""Plugin loading for in-process detectors (v0.5.0).

Discovers third-party in-process detectors via the
``z_llm_safety_gateway.detectors`` entry point group and registers them into
the gateway's :class:`DetectorRegistry` (DESIGN.md Section 7.2/7.6.1).

Module-level helpers also expose the discovered plugin names to config
validation so unknown-detector errors can list plugin-provided detectors.
"""

from __future__ import annotations

import logging

from z_llm_safety_gateway.detectors.registry import DetectorRegistry

logger = logging.getLogger(__name__)

#: Entry point group under which third-party detectors are registered.
PLUGIN_ENTRY_POINT_GROUP = "z_llm_safety_gateway.detectors"

#: Lazily-populated cache of plugin names discovered from entry points.
#: Populated by :func:`discover_plugin_names` and reused by config validation.
_plugin_names: frozenset[str] = frozenset()


def load_plugins(registry: DetectorRegistry) -> int:
    """Discover and register in-process plugin detectors into *registry*.

    Args:
        registry: The gateway's detector registry (built-ins already
            registered).  Plugins with a name that already exists are skipped
            so built-ins always win.

    Returns:
        The number of plugins successfully registered.
    """
    count = registry.register_from_entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    if count:
        logger.info("loaded %d in-process plugin detector(s)", count)
    return count


def discover_plugin_names() -> frozenset[str]:
    """Return the names of all entry-point-discovered plugin detectors.

    Cached on first call.  Used by config validation to include discovered
    plugin names in the "unknown detector" error message.

    Returns:
        A frozenset of plugin detector names.
    """
    global _plugin_names
    if _plugin_names:
        return _plugin_names
    from importlib.metadata import entry_points

    names = {
        ep.name for ep in entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    }
    _plugin_names = frozenset(names)
    return _plugin_names


def register_plugins_for_validation(registry: DetectorRegistry | None = None) -> None:
    """Ensure discovered plugin names are visible for config validation.

    Loads the plugin name cache so ``_validate_detector_name`` can include
    discovered plugins in the "available detectors" list.  If *registry* is
    provided, plugins are also registered into it.

    Args:
        registry: Optional registry to register plugins into.
    """
    discover_plugin_names()
    if registry is not None:
        load_plugins(registry)
