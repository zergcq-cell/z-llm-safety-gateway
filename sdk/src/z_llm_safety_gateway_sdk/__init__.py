"""z_llm_safety_gateway_sdk — Detector SDK for the z LLM Safety Gateway.

A separate SDK package enabling third-party detector development without
installing the full gateway (DESIGN.md Section 7.4).
"""

from z_llm_safety_gateway_sdk.base import Detector
from z_llm_safety_gateway_sdk.context import DetectionContext
from z_llm_safety_gateway_sdk.modification import Modification
from z_llm_safety_gateway_sdk.result import DetectionResult

__version__ = "1.0.0"

__all__ = [
    "Detector",
    "DetectionContext",
    "DetectionResult",
    "Modification",
    "__version__",
]
