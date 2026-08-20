"""Detector framework: abstract base class, registry, and public exports.

This package exports the core detector abstractions (Detector, DetectorRegistry)
as well as all built-in detector implementations and a helper to create a
pre-registered registry.
"""

from __future__ import annotations

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.pii import PIIDetector
from z_llm_safety_gateway.detectors.prompt_injection import PromptInjectionDetector
from z_llm_safety_gateway.detectors.registry import DetectorRegistry
from z_llm_safety_gateway.detectors.secret_leak import SecretLeakDetector
from z_llm_safety_gateway.detectors.sensitive_words import SensitiveWordsDetector
from z_llm_safety_gateway.detectors.status import (
    DetectorReasonCode,
    DetectorState,
    DetectorStatus,
    DetectorStatusRegistry,
)
from z_llm_safety_gateway.detectors.toxicity import ToxicityDetector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

__all__ = [
    "DetectionContext",
    "DetectionResult",
    "Detector",
    "DetectorRegistry",
    "DetectorReasonCode",
    "DetectorState",
    "DetectorStatus",
    "DetectorStatusRegistry",
    "PromptInjectionDetector",
    "PIIDetector",
    "SensitiveWordsDetector",
    "SecretLeakDetector",
    "ToxicityDetector",
    "create_default_registry",
]


def create_default_registry() -> DetectorRegistry:
    """Create a DetectorRegistry with all built-in detectors registered.

    Returns:
        A DetectorRegistry instance with prompt_injection, pii,
        sensitive_words, secret_leak, and toxicity detectors registered.
    """
    registry = DetectorRegistry()
    registry.register("prompt_injection", PromptInjectionDetector)
    registry.register("pii_redaction", PIIDetector)
    registry.register("sensitive_words", SensitiveWordsDetector)
    registry.register("secret_leak", SecretLeakDetector)
    registry.register("toxicity", ToxicityDetector)
    return registry
