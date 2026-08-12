"""Unit tests for PostAuditRunner.

Covers TC-PAR-001 through TC-PAR-004 (post-audit-recall spec).
"""

from __future__ import annotations

import asyncio

from z_llm_safety_gateway.models import DetectionResult
from z_llm_safety_gateway.pipeline.engine import PipelineResult
from z_llm_safety_gateway.post_audit.audit import PostAuditRunner


class _FakeEngine:
    def __init__(self, result: PipelineResult | None = None) -> None:
        self.result = result or PipelineResult(
            final_action="allow", overall_risk_level="low"
        )
        self.calls: list[dict] = []

    async def run(self, detectors, contexts, configs):
        content = contexts[0].metadata["content"] if contexts else ""
        self.calls.append({"content": content, "n_detectors": len(detectors)})
        return self.result


def _block_result() -> PipelineResult:
    return PipelineResult(
        final_action="block",
        overall_risk_level="critical",
        detector_results=[
            DetectionResult(
                detector_name="secret_leak",
                category="secret",
                action="block",
                confidence=0.99,
                risk_level="critical",
                message="API key leaked",
            )
        ],
    )


def _modify_result() -> PipelineResult:
    return PipelineResult(
        final_action="modify",
        overall_risk_level="high",
        detector_results=[
            DetectionResult(
                detector_name="pii_redaction",
                category="pii",
                action="modify",
                confidence=0.9,
                risk_level="high",
                message="pii found",
                modified_content="masked",
            )
        ],
    )


# --------------------------------------------------------------------------- #
# TC-PAR-001: post-audit runs on full accumulated response
# --------------------------------------------------------------------------- #
def test_post_audit_runs_on_full_content():
    """TC-PAR-001: post-audit detects on the complete accumulated response."""
    engine = _FakeEngine()
    runner = PostAuditRunner(
        engine=engine, output_detectors=["secret_leak"], detector_configs={}
    )
    asyncio.run(runner.run("full accumulated response content"))
    assert engine.calls
    assert engine.calls[0]["content"] == "full accumulated response content"
    assert engine.calls[0]["n_detectors"] == 1


# --------------------------------------------------------------------------- #
# TC-PAR-002: uses output detectors with consistent thresholds
# --------------------------------------------------------------------------- #
def test_post_audit_uses_output_detectors():
    """TC-PAR-002: post-audit uses all enabled output detectors."""
    engine = _FakeEngine()
    runner = PostAuditRunner(
        engine=engine,
        output_detectors=["secret_leak", "toxicity"],
        detector_configs={},
    )
    asyncio.run(runner.run("some content"))
    assert engine.calls[0]["n_detectors"] == 2


# --------------------------------------------------------------------------- #
# TC-PAR-003: post-audit modify downgraded to flag
# --------------------------------------------------------------------------- #
def test_post_audit_modify_downgraded_to_flag():
    """TC-PAR-003: post-audit modify downgrades to flag with audit fields."""
    engine = _FakeEngine(_modify_result())
    runner = PostAuditRunner(engine=engine, output_detectors=["pii_redaction"], detector_configs={})
    outcome = asyncio.run(runner.run("pii content"))
    assert outcome.effective_action == "flag"
    assert outcome.original_action == "modify"
    assert outcome.applied is False


# --------------------------------------------------------------------------- #
# TC-PAR-004: post-audit block triggers recall
# --------------------------------------------------------------------------- #
def test_post_audit_block_triggers_recall():
    """TC-PAR-004: post-audit block result is flagged for recall."""
    engine = _FakeEngine(_block_result())
    runner = PostAuditRunner(engine=engine, output_detectors=["secret_leak"], detector_configs={})
    outcome = asyncio.run(runner.run("secret content"))
    assert outcome.effective_action == "block"
    assert outcome.recall_needed is True
    assert outcome.risk_level == "critical"
    assert outcome.category == "secret"
    assert outcome.reason == "API key leaked"
