"""Toxicity detector using the unitary/toxic-bert model via transformers.

Detects toxic content using the ``unitary/toxic-bert`` model loaded through
the HuggingFace ``transformers`` pipeline API. The model is lazily loaded on
the first ``detect()`` call — ``initialize()`` only stores configuration.

Key design decisions (per design.md Decision 9):

- **Lazy loading**: The ML model is NOT loaded during ``initialize()``. It is
  loaded on the first ``detect()`` call and reused for subsequent calls.
- **Lazy imports**: ``transformers`` and ``torch`` are imported inside
  ``_load_model()``, not at module level, so the package can be installed
  without ML dependencies.
- **Offline mode**: When ``offline_mode=True``, ``HF_HUB_OFFLINE=1`` is set
  before loading to prevent network requests.
- **Error handling**: Model loading failures are handled according to the
  ``on_error`` strategy (``fail_open`` or ``fail_closed``).
- **Threshold delegation**: The detector only computes a confidence score;
  the pipeline engine overrides the action via ``ThresholdDecisionEngine``.

Spec: toxicity-detector/spec.yaml (REQ-001 to REQ-008).
"""

from __future__ import annotations

import os
import time
from typing import Any, Literal

import structlog

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

# Default configuration values (per spec REQ-005, REQ-008).
_DEFAULT_MODEL_NAME = "unitary/toxic-bert"
_DEFAULT_ON_ERROR = "fail_open"
_DEFAULT_BLOCK_THRESHOLD = 0.90
_DEFAULT_FLAG_THRESHOLD = 0.60


class ToxicityDetector(Detector):
    """Detector for toxic content using the unitary/toxic-bert model.

    Configuration keys (passed to ``initialize``):

    - ``model_name``: HuggingFace model identifier
      (default: ``"unitary/toxic-bert"``).
    - ``model_cache_dir``: Local directory for model files
      (default: ``None`` → uses transformers global cache).
    - ``model_version``: HuggingFace Hub revision/tag
      (default: ``None`` → latest).
    - ``offline_mode``: If ``True``, prevent network requests during model
      loading (default: ``False``).
    - ``on_error``: Error strategy — ``"fail_open"`` or ``"fail_closed"``
      (default: ``"fail_open"``).
    - ``block_threshold``: Confidence at or above which action is ``block``
      (default: ``0.90``).
    - ``flag_threshold``: Confidence at or above which (but below
      ``block_threshold``) action is ``flag`` (default: ``0.60``).
    """

    name: str = "toxicity"
    category: str = "toxicity"
    description: str = (
        "Detects toxic content using the unitary/toxic-bert model "
        "via the HuggingFace transformers pipeline"
    )
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._model_name: str = _DEFAULT_MODEL_NAME
        self._model_cache_dir: str | None = None
        self._model_version: str | None = None
        self._offline_mode: bool = False
        self._on_error: str = _DEFAULT_ON_ERROR
        self._block_threshold: float = _DEFAULT_BLOCK_THRESHOLD
        self._flag_threshold: float = _DEFAULT_FLAG_THRESHOLD

    async def initialize(self, config: dict[str, Any]) -> None:
        """Store configuration parameters without loading the model.

        Per REQ-008 / SC-016: ``initialize()`` only stores configuration.
        The model is lazily loaded on the first ``detect()`` call.

        Args:
            config: Detector configuration dict. See class docstring for
                supported keys.
        """
        self._model_name = config.get("model_name", _DEFAULT_MODEL_NAME)
        self._model_cache_dir = config.get("model_cache_dir")
        self._model_version = config.get("model_version")
        self._offline_mode = config.get("offline_mode", False)
        self._on_error = config.get("on_error", _DEFAULT_ON_ERROR)
        self._block_threshold = config.get(
            "block_threshold", _DEFAULT_BLOCK_THRESHOLD
        )
        self._flag_threshold = config.get(
            "flag_threshold", _DEFAULT_FLAG_THRESHOLD
        )

        logger.info(
            "toxicity_detector_initialized",
            model_name=self._model_name,
            model_cache_dir=self._model_cache_dir,
            model_version=self._model_version,
            offline_mode=self._offline_mode,
            on_error=self._on_error,
            block_threshold=self._block_threshold,
            flag_threshold=self._flag_threshold,
        )

    async def detect(
        self, content: str, context: DetectionContext
    ) -> DetectionResult:
        """Run toxicity detection on the given content.

        On the first call, the model is lazily loaded. If loading fails,
        the error is handled according to the ``on_error`` strategy.

        The detector only computes a confidence score (the model's toxicity
        score) and returns a placeholder ``action="allow"``. The pipeline
        engine overrides the action using ``ThresholdDecisionEngine`` based
        on the configured thresholds.

        Args:
            content: The text content to analyze.
            context: Detection context with direction, request_id, etc.

        Returns:
            A DetectionResult with the computed confidence, risk level,
            and model details. On error, returns a result based on the
            ``on_error`` strategy.
        """
        start = time.perf_counter()

        # Lazy load model on first call.
        if self._pipeline is None:
            try:
                await self._load_model()
            except Exception as exc:
                logger.error(
                    "toxicity_model_load_failed",
                    model_name=self._model_name,
                    error=str(exc),
                    on_error=self._on_error,
                )
                return self._make_error_result(exc, start)

        # Run inference.
        try:
            results = self._pipeline(content, top_k=None)
        except Exception as exc:
            logger.error(
                "toxicity_inference_failed",
                model_name=self._model_name,
                error=str(exc),
                on_error=self._on_error,
            )
            return self._make_error_result(exc, start)

        # Extract toxicity score from model output.
        confidence = self._extract_toxicity_score(results)
        risk_level = self._compute_risk_level(confidence)

        if confidence > 0:
            message = f"Toxicity detected (score: {confidence:.2f})"
        else:
            message = "No toxicity detected"

        duration_ms = (time.perf_counter() - start) * 1000

        logger.debug(
            "toxicity_detection_complete",
            confidence=confidence,
            risk_level=risk_level,
            model_name=self._model_name,
            duration_ms=duration_ms,
        )

        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",  # Placeholder — pipeline engine overrides via thresholds
            confidence=confidence,
            risk_level=risk_level,
            message=message,
            details={
                "model": self._model_name,
                "toxicity_score": confidence,
                "model_loaded": True,
            },
            duration_ms=duration_ms,
        )

    async def _load_model(self) -> None:
        """Lazily load the toxic-bert model using transformers pipeline.

        Imports ``transformers`` inside this method so the package can be
        installed without ML dependencies. When ``offline_mode`` is True,
        sets ``HF_HUB_OFFLINE=1`` to prevent network requests.

        Raises:
            RuntimeError: If the ``transformers`` library is not installed.
            Exception: Any exception from the transformers pipeline
                constructor (e.g., model not found, network error).
        """
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise RuntimeError(
                "transformers library is not installed. "
                "Install with: pip install z-llm-safety-gateway[ml]"
            ) from exc

        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "device": "cpu",
        }
        if self._model_cache_dir:
            kwargs["cache_dir"] = self._model_cache_dir
        if self._model_version:
            kwargs["revision"] = self._model_version

        if self._offline_mode:
            os.environ["HF_HUB_OFFLINE"] = "1"
            logger.info(
                "toxicity_offline_mode_enabled",
                model_name=self._model_name,
            )

        logger.info(
            "toxicity_loading_model",
            model_name=self._model_name,
            model_cache_dir=self._model_cache_dir,
            model_version=self._model_version,
            offline_mode=self._offline_mode,
        )

        self._pipeline = pipeline("text-classification", **kwargs)

    @staticmethod
    def _extract_toxicity_score(results: Any) -> float:
        """Extract the toxicity score from the model's pipeline output.

        The transformers pipeline returns a list of dicts with ``label``
        and ``score`` keys. This method finds the ``"toxic"`` label's score
        if present; otherwise it takes the maximum score across all labels.

        Handles both single-prediction and multi-label outputs, as well as
        batch-mode nested lists.

        Args:
            results: The output from ``pipeline(content)``.

        Returns:
            A float in ``[0.0, 1.0]`` representing the toxicity confidence.
        """
        if not results:
            return 0.0

        # Handle batch-mode nested lists: [[{...}, {...}], ...]
        if isinstance(results, list) and len(results) > 0 and isinstance(
            results[0], list
        ):
            results = results[0]

        if not isinstance(results, list):
            return 0.0

        # Look for the "toxic" label first.
        for item in results:
            if isinstance(item, dict) and item.get("label") == "toxic":
                score = float(item.get("score", 0.0))
                return max(0.0, min(1.0, score))

        # No "toxic" label found — take the maximum score.
        scores = [
            float(item.get("score", 0.0))
            for item in results
            if isinstance(item, dict)
        ]
        if not scores:
            return 0.0

        return max(0.0, min(1.0, max(scores)))

    @staticmethod
    def _compute_risk_level(
        confidence: float,
    ) -> Literal["low", "medium", "high", "critical"]:
        """Map a confidence score to a risk level.

        Args:
            confidence: Confidence score in ``[0.0, 1.0]``.

        Returns:
            One of ``"low"``, ``"medium"``, ``"high"``, or ``"critical"``.
        """
        if confidence >= 0.90:
            return "critical"
        if confidence >= 0.60:
            return "high"
        if confidence > 0:
            return "medium"
        return "low"

    def _make_error_result(
        self, exc: Exception, start: float
    ) -> DetectionResult:
        """Create a DetectionResult for a model loading or inference failure.

        - ``fail_open`` → action="allow", confidence=0.0 (request continues)
        - ``fail_closed`` → action="block", confidence=1.0 (request blocked)

        Args:
            exc: The exception that caused the failure.
            start: Performance counter value at the start of detect().

        Returns:
            A DetectionResult with the error details and appropriate action.
        """
        duration_ms = (time.perf_counter() - start) * 1000
        error_msg = str(exc)

        if self._on_error == "fail_closed":
            return DetectionResult(
                detector_name=self.name,
                category=self.category,
                action="block",
                confidence=1.0,
                risk_level="high",
                message=f"Model loading failed (fail_closed): {error_msg}",
                error=error_msg,
                details={
                    "model": self._model_name,
                    "model_loaded": False,
                },
                duration_ms=duration_ms,
            )

        # fail_open (default)
        return DetectionResult(
            detector_name=self.name,
            category=self.category,
            action="allow",
            confidence=0.0,
            risk_level="low",
            message=f"Model loading failed (fail_open): {error_msg}",
            error=error_msg,
            details={
                "model": self._model_name,
                "model_loaded": False,
            },
            duration_ms=duration_ms,
        )
