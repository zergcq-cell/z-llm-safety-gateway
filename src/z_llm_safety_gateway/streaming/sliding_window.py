"""Character-based sliding window for streaming detection (v0.3.0).

Implements DESIGN.md Section 8.2 sliding-window detection using character
counts (tokenizer-agnostic).  A window triggers detection once ``window_size``
characters accumulate; after detection the window slides forward by
``window_size - overlap`` characters, retaining the last ``overlap`` characters
so cross-boundary content is re-checked in the next window.
"""

from __future__ import annotations


class SlidingWindow:
    """Accumulates characters and exposes full windows for detection.

    Args:
        window_size: Number of characters per window.
        overlap: Number of trailing characters retained between windows.
    """

    def __init__(self, window_size: int = 200, overlap: int = 50) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if overlap < 0 or overlap >= window_size:
            raise ValueError("overlap must be >= 0 and < window_size")
        self._window_size = window_size
        self._overlap = overlap
        self._buffer = ""

    @property
    def buffer(self) -> str:
        """Return the current accumulated character buffer."""
        return self._buffer

    @property
    def size(self) -> int:
        """Return the current buffer length in characters."""
        return len(self._buffer)

    def append(self, text: str) -> None:
        """Append *text* to the accumulation buffer."""
        self._buffer += text

    def is_ready(self) -> bool:
        """Return True when the buffer has reached ``window_size`` characters."""
        return len(self._buffer) >= self._window_size

    def consume_window(self) -> tuple[str, str]:
        """Extract the current window and slide forward.

        Returns:
            A ``(content, retained)`` tuple where *content* is the full window
            passed to detection and *retained* is the trailing ``overlap``
            characters kept for the next window.  Returns ``("", buffer)`` when
            the buffer has not yet reached ``window_size``.
        """
        if len(self._buffer) < self._window_size:
            return "", self._buffer

        content = self._buffer[: self._window_size]
        retained = self._buffer[self._window_size - self._overlap :]
        # Slide: keep the trailing overlap as the start of the next buffer.
        self._buffer = retained
        return content, retained
