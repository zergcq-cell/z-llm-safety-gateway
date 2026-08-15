"""Accuracy tests for built-in rule-based detectors.

Loads fixed sample sets from ``tests/accuracy/samples/`` and asserts that
each detector achieves the configured accuracy on them.  The samples are
offline, deterministic, and serve as regression protection for detection
quality (a detector change must not silently degrade accuracy).

Covered detectors (rule-based, no model/network dependency):
- prompt_injection
- secret_leak
- sensitive_words   (uses a fixed inline word list)
- pii_redaction

The ML-based toxicity detector is covered by a smoke test only; true
accuracy validation requires a model environment (skipped otherwise).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from z_llm_safety_gateway.detectors import create_default_registry
from z_llm_safety_gateway.models import DetectionContext

SAMPLES_DIR = Path(__file__).parent / "samples"
ACCURACY_THRESHOLD = 0.9
FALSE_POSITIVE_RATE_LIMIT = 0.1

# Fixed config for sensitive_words so samples are deterministic.
SENSITIVE_WORDS_CONFIG = {
    "words": ["urgent money transfer", "password reset link", "account suspended"],
    "count_block_threshold": 1,
    "count_flag_threshold": 1,
}

# PromptInjectionDetector returns action="allow" placeholder; the pipeline
# engine decides the final action from confidence.  SEVERITY_SCORES are
# high=0.5/medium=0.3/low=0.15; treat confidence >= 0.4 (any high-severity
# match, or a combination) as "recognized as injection".
INJECTION_CONFIDENCE_THRESHOLD = 0.4


def _load_samples(name: str) -> tuple[list[str], list[str]]:
    """Load (positive_contents, negative_contents) for a detector sample set."""
    data = yaml.safe_load((SAMPLES_DIR / f"{name}.yaml").read_text())
    positives = [s["content"] for s in data["positive"]]
    negatives = [s["content"] for s in data["negative"]]
    assert len(positives) >= 20, f"{name}: need >=20 positive samples"
    assert len(negatives) >= 20, f"{name}: need >=20 negative samples"
    return positives, negatives


async def _evaluate(name: str, config: dict | None = None) -> dict[str, float]:
    """Run the detector over its samples; return accuracy metrics."""
    registry = create_default_registry()
    detector_cls = registry.get(name)
    detector = detector_cls()
    await detector.initialize(config or {})

    positives, negatives = _load_samples(name)
    ctx = DetectionContext(direction="input", request_id=f"acc-{name}")

    def _is_blocked(result) -> bool:
        # prompt_injection uses confidence; others set action explicitly.
        if name == "prompt_injection":
            return result.confidence >= INJECTION_CONFIDENCE_THRESHOLD
        return result.action != "allow"

    correct = 0
    for content in positives:
        result = await detector.detect(content, ctx)
        if _is_blocked(result):
            correct += 1

    false_positives = 0
    for content in negatives:
        result = await detector.detect(content, ctx)
        if _is_blocked(result):
            false_positives += 1

    n = len(positives) + len(negatives)
    return {
        "accuracy": (correct + (len(negatives) - false_positives)) / n,
        "false_positive_rate": false_positives / len(negatives),
        "precision_positive": correct / len(positives),
    }


@pytest.mark.asyncio
async def test_prompt_injection_accuracy() -> None:
    """TC-ACC-002: prompt_injection accuracy >= 0.9, FPR <= 0.1."""
    metrics = await _evaluate("prompt_injection")
    assert metrics["accuracy"] >= ACCURACY_THRESHOLD, metrics
    assert metrics["false_positive_rate"] <= FALSE_POSITIVE_RATE_LIMIT, metrics


@pytest.mark.asyncio
async def test_secret_leak_accuracy() -> None:
    """TC-ACC-002: secret_leak accuracy >= 0.9, FPR <= 0.1."""
    metrics = await _evaluate("secret_leak")
    assert metrics["accuracy"] >= ACCURACY_THRESHOLD, metrics
    assert metrics["false_positive_rate"] <= FALSE_POSITIVE_RATE_LIMIT, metrics


@pytest.mark.asyncio
async def test_sensitive_words_accuracy() -> None:
    """TC-ACC-002: sensitive_words accuracy >= 0.9, FPR <= 0.1 (fixed word list)."""
    metrics = await _evaluate("sensitive_words", SENSITIVE_WORDS_CONFIG)
    assert metrics["accuracy"] >= ACCURACY_THRESHOLD, metrics
    assert metrics["false_positive_rate"] <= FALSE_POSITIVE_RATE_LIMIT, metrics


@pytest.mark.asyncio
async def test_pii_redaction_accuracy() -> None:
    """TC-ACC-002: pii_redaction accuracy >= 0.9, FPR <= 0.1."""
    metrics = await _evaluate("pii_redaction")
    assert metrics["accuracy"] >= ACCURACY_THRESHOLD, metrics
    assert metrics["false_positive_rate"] <= FALSE_POSITIVE_RATE_LIMIT, metrics


@pytest.mark.asyncio
async def test_toxicity_smoke_without_model() -> None:
    """TC-ACC-003: toxicity smoke test without model environment.

    The ML model is not loaded in CI; the detector must either load via
    offline mode or be skipped.  This guards that the accuracy suite does
    not break when the model is unavailable.
    """
    registry = create_default_registry()
    try:
        detector_cls = registry.get("toxicity")
    except KeyError:
        pytest.skip("toxicity detector not registered")
    detector = detector_cls()

    async def _try_init() -> bool:
        try:
            await detector.initialize({"offline_mode": True})
            return True
        except Exception:
            return False

    if not await _try_init():
        pytest.skip("toxicity model environment unavailable; smoke test skipped")


@pytest.mark.asyncio
async def test_sample_sets_complete() -> None:
    """TC-ACC-001: all four rule-based sample sets exist and are well-formed."""
    for name in ("prompt_injection", "secret_leak", "sensitive_words", "pii_redaction"):
        positives, negatives = _load_samples(name)
        assert len(positives) >= 20
        assert len(negatives) >= 20
