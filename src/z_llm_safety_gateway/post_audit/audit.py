"""Post-audit detection runner (v0.3.0).

Implements DESIGN.md Section 8.3: after a streaming response completes and
``[DONE]`` is sent, a background deep-detection pass runs on the full
accumulated response to catch risks the sliding window may have missed
(e.g. secrets spanning chunk boundaries).  Post-audit results are downgraded
appropriately (modify -> flag, since the response is already sent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from z_llm_safety_gateway.pipeline.engine import PipelineEngine, PipelineResult


@dataclass
class PostAuditOutcome:
    """Result of a post-audit detection pass.

    Attributes:
        effective_action: The action after downgrading.  ``modify`` becomes
            ``flag`` because the response has already been streamed.
        original_action: The raw ``final_action`` from the pipeline.
        applied: Whether the action could be applied to the already-sent
            response (always False for modify in post-audit).
        risk_level: The overall risk level.
        category: The category of the triggering detector (if any).
        reason: The message of the triggering detector (if any).
        recall_needed: Whether a recall signal should be sent (True when the
            effective action is ``block``).
    """

    effective_action: str = "allow"
    original_action: str = "allow"
    applied: bool = False
    risk_level: str = "low"
    category: str | None = None
    reason: str | None = None
    recall_needed: bool = False


class PostAuditRunner:
    """Runs deep detection on a full accumulated response.

    Args:
        engine: The PipelineEngine used for detection.
        output_detectors: List of initialized output Detector instances.
        detector_configs: Detector name → config dict mapping.
    """

    def __init__(
        self,
        engine: PipelineEngine,
        output_detectors: list[Any],
        detector_configs: dict[str, dict[str, Any]],
    ) -> None:
        self._engine = engine
        self._detectors = output_detectors
        self._configs = detector_configs

    async def run(self, content: str) -> PostAuditOutcome:
        """Run post-audit detection on *content* and return the outcome."""
        from z_llm_safety_gateway.models import DetectionContext

        context = DetectionContext(
            direction="output",
            request_id="",
            metadata={"content": content},
        )
        result: PipelineResult = await self._engine.run(
            self._detectors, [context], self._configs
        )

        original = result.final_action
        effective = original
        applied = True

        # modify cannot be applied post-stream; downgrade to flag.
        if original == "modify":
            effective = "flag"
            applied = False

        # block requires recall (response already delivered).
        recall_needed = effective == "block"

        trigger = result.detector_results[0] if result.detector_results else None
        return PostAuditOutcome(
            effective_action=effective,
            original_action=original,
            applied=applied,
            risk_level=result.overall_risk_level,
            category=trigger.category if trigger else None,
            reason=trigger.message if trigger else None,
            recall_needed=recall_needed,
        )
