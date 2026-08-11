"""Threshold-driven decision engine for detector action determination.

Implements the separation between detector confidence computation and action
decision as required by DESIGN.md Section 5.3 and design.md Decision 5.
Detectors only compute a confidence score; the ThresholdDecisionEngine maps
that score to an action (block / flag / allow) using per-detector thresholds.
"""

from __future__ import annotations

from typing import Literal

Action = Literal["allow", "block", "flag"]


class ThresholdDecisionEngine:
    """Maps a detector confidence score to an action using thresholds.

    The engine is stateless; :meth:`decide` is a pure function that can be
    called as a static method or via an instance.

    Decision rules (per design.md Decision 5):

    - ``confidence >= block_threshold`` → ``"block"``
    - ``flag_threshold <= confidence < block_threshold`` → ``"flag"``
    - ``confidence < flag_threshold`` → ``"allow"``
    """

    @staticmethod
    def decide(
        confidence: float,
        block_threshold: float,
        flag_threshold: float,
    ) -> Action:
        """Determine the action for a given confidence and threshold pair.

        Args:
            confidence: Detector confidence score in ``[0.0, 1.0]``.
            block_threshold: Confidence at or above which the action is block.
            flag_threshold: Confidence at or above which (but below
                ``block_threshold``) the action is flag.

        Returns:
            One of ``"block"``, ``"flag"``, or ``"allow"``.
        """
        if confidence >= block_threshold:
            return "block"
        if confidence >= flag_threshold:
            return "flag"
        return "allow"
