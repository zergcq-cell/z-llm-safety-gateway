"""Streaming memory management (v0.3.0).

Implements DESIGN.md Section 8.5: caps the accumulated streaming response to
prevent OOM.  ``max_response_size`` is a byte-based limit; ``on_max_size``
selects ``block`` (stop stream + safety_block) or ``truncate`` (stop
accumulating, continue streaming).
"""

from __future__ import annotations

import re


class SizeLimit:
    """Parse and represent a byte-based size limit.

    Supports plain byte counts (``"512"``) and suffixed values (``"1KB"``,
    ``"1MB"``).  Case-insensitive.
    """

    _PATTERN = re.compile(r"^(\d+)\s*(b|kb|mb|gb)?$", re.IGNORECASE)
    _MULTIPLIERS = {"": 1, "b": 1, "kb": 1024, "mb": 1024 * 1024, "gb": 1024**3}

    def __init__(self, value: str) -> None:
        self._bytes = self.parse(value)

    @staticmethod
    def parse(value: str) -> int:
        """Parse *value* into a byte count."""
        match = SizeLimit._PATTERN.match(str(value).strip())
        if not match:
            raise ValueError(f"Invalid size limit: '{value}'")
        amount = int(match.group(1))
        unit = (match.group(2) or "").lower()
        return amount * SizeLimit._MULTIPLIERS[unit]

    @property
    def bytes(self) -> int:
        """Return the limit in bytes."""
        return self._bytes


class StreamingMemory:
    """Tracks accumulated response size and enforces the size policy.

    Args:
        max_response_size: Byte-based accumulation limit (e.g. ``"1MB"``).
        on_max_size: ``"block"`` or ``"truncate"``.
    """

    def __init__(self, max_response_size: str = "1MB", on_max_size: str = "block") -> None:
        if on_max_size not in ("block", "truncate"):
            raise ValueError(
                f"on_max_size must be 'block' or 'truncate', got '{on_max_size}'"
            )
        self._limit = SizeLimit(max_response_size)
        self._policy = on_max_size

    @property
    def policy(self) -> str:
        """Return the configured policy (``block`` or ``truncate``)."""
        return self._policy

    def check_exceeded(self, accumulated_content: str) -> bool:
        """Return True if *accumulated_content* exceeds the size limit (bytes).

        Content is encoded as UTF-8 so multi-byte characters (e.g. Chinese)
        are counted correctly against the byte-based limit.
        """
        byte_size = len(accumulated_content.encode("utf-8"))
        return byte_size >= self._limit.bytes
