"""Result aggregator for collecting and merging DetectionResults.

Implements the aggregation strategy described in DESIGN.md Section 5.5 and
design.md Decision 6:

- ``final_action``: highest-precedence action (block > modify > flag > allow)
- ``overall_risk_level``: highest risk level (critical > high > medium > low)
- ``modifications``: extracted from ``modify`` results, sorted by detector
  priority (ascending — lower number = higher priority = applied first)
- ``risk_profile``: all ``flag`` results for audit logging
- Optional flag escalation: if a :class:`FlagEscalationRule` is configured and
  evaluates to ``True``, ``final_action`` is upgraded from ``flag`` to ``block``
"""

from __future__ import annotations

from dataclasses import dataclass, field

from z_llm_safety_gateway.models import DetectionResult, Modification
from z_llm_safety_gateway.pipeline.flag_escalation import FlagEscalationRule

# Action precedence: higher number = higher priority.
_ACTION_PRECEDENCE: dict[str, int] = {
    "allow": 0,
    "flag": 1,
    "modify": 2,
    "block": 3,
}

# Risk-level ordering: higher number = more severe.
_RISK_LEVEL_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


@dataclass
class AggregatedResult:
    """Output of :meth:`ResultAggregator.aggregate`.

    Attributes:
        final_action: The highest-precedence action across all results.
        overall_risk_level: The highest risk level across all results.
        modifications: Modify results converted to Modification objects,
            sorted by detector priority (ascending).
        risk_profile: All flag DetectionResults, for audit logging.
    """

    final_action: str = "allow"
    overall_risk_level: str = "low"
    modifications: list[Modification] = field(default_factory=list)
    risk_profile: list[DetectionResult] = field(default_factory=list)


class ResultAggregator:
    """Aggregates a list of DetectionResults into a unified pipeline outcome.

    Args:
        flag_escalation: Optional compiled escalation rule. When provided and
            the aggregated ``final_action`` is ``"flag"``, the rule is
            evaluated; if it returns ``True``, ``final_action`` is upgraded
            to ``"block"``.
    """

    def __init__(self, flag_escalation: FlagEscalationRule | None = None) -> None:
        self._flag_escalation = flag_escalation

    def aggregate(
        self,
        results: list[DetectionResult],
        priorities: dict[str, int] | None = None,
        message_indices: list[int | None] | None = None,
    ) -> AggregatedResult:
        """Aggregate detection results into a single pipeline outcome.

        Args:
            results: All completed DetectionResults from the pipeline run.
            priorities: Mapping of detector name to priority value. Used to
                sort modifications. Defaults to priority 100 for unknown names.
            message_indices: List parallel to *results*; ``message_indices[i]``
                is the message index associated with ``results[i]``. Defaults
                to ``None`` for all results if not provided.

        Returns:
            An :class:`AggregatedResult` with the merged fields.
        """
        priorities = priorities or {}
        msg_indices = message_indices or [None] * len(results)

        # --- final_action: highest precedence ---
        final_action = "allow"
        for r in results:
            if _ACTION_PRECEDENCE[r.action] > _ACTION_PRECEDENCE[final_action]:
                final_action = r.action

        # --- overall_risk_level: highest severity ---
        overall_risk_level = "low"
        for r in results:
            if _RISK_LEVEL_ORDER[r.risk_level] > _RISK_LEVEL_ORDER[overall_risk_level]:
                overall_risk_level = r.risk_level

        # --- modifications: from modify results, sorted by priority ---
        modifications: list[Modification] = []
        for i, r in enumerate(results):
            if r.action == "modify" and r.modified_content is not None:
                modifications.append(
                    Modification(
                        detector_name=r.detector_name,
                        modified_content=r.modified_content,
                        priority=priorities.get(r.detector_name, 100),
                        message_index=msg_indices[i] if i < len(msg_indices) else None,
                    )
                )
        # Sort by priority ascending (lower number = applied first).
        modifications.sort(key=lambda m: m.priority)

        # --- risk_profile: all flag results ---
        risk_profile = [r for r in results if r.action == "flag"]

        # --- flag escalation (optional) ---
        if (
            self._flag_escalation is not None
            and final_action == "flag"
            and self._flag_escalation.evaluate(risk_profile)
        ):
            final_action = "block"

        return AggregatedResult(
            final_action=final_action,
            overall_risk_level=overall_risk_level,
            modifications=modifications,
            risk_profile=risk_profile,
        )
