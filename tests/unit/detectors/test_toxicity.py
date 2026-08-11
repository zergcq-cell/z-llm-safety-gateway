"""Tests for ToxicityDetector — TC-TOX-001 to TC-TOX-016.

Covers toxicity detection using the unitary/toxic-bert model via the
transformers pipeline API, with lazy model loading, offline mode support,
config-driven cache_dir and model_version, threshold-driven decisions, and
on_error strategies for model loading failures.

The transformers and torch libraries are NOT installed in the test
environment. All tests mock the transformers library by injecting a mock
module into ``sys.modules`` so that the lazy import inside
``ToxicityDetector._load_model()`` succeeds.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from z_llm_safety_gateway.detectors.base import Detector
from z_llm_safety_gateway.detectors.toxicity import ToxicityDetector
from z_llm_safety_gateway.models import DetectionContext, DetectionResult
from z_llm_safety_gateway.pipeline.threshold import ThresholdDecisionEngine

# Threshold values matching the spec (REQ-005).
_BLOCK_THRESHOLD = 0.90
_FLAG_THRESHOLD = 0.60


def _make_context(direction: str = "input") -> DetectionContext:
    """Create a minimal DetectionContext for testing."""
    return DetectionContext(direction=direction, request_id="req-test-001")


@contextmanager
def mock_transformers(
    return_value: list[dict[str, Any]] | None = None,
    side_effect: Exception | None = None,
):
    """Context manager that mocks the transformers library.

    Injects a mock module into ``sys.modules`` so that the lazy import
    inside ``ToxicityDetector._load_model()`` resolves to the mock.

    The mock simulates the two-level calling pattern of transformers:

    1. ``pipeline("text-classification", **kwargs)`` returns a callable
       (the inference pipeline object).
    2. Calling that object with ``content`` returns the model output
       (a list of ``{"label": ..., "score": ...}`` dicts).

    Args:
        return_value: The list of dicts to return from pipeline inference.
            Defaults to ``[{"label": "toxic", "score": 0.95}]``.
        side_effect: Exception to raise when ``pipeline()`` is called (for
            testing model load failures). When set, ``return_value`` is
            ignored.

    Yields:
        The mock pipeline function (``MagicMock``) for assertion checking.
    """
    mock_module = MagicMock()
    mock_pipeline_fn = MagicMock()

    if side_effect is not None:
        mock_pipeline_fn.side_effect = side_effect
    else:
        mock_inference = MagicMock(
            return_value=return_value or [{"label": "toxic", "score": 0.95}]
        )
        mock_pipeline_fn.return_value = mock_inference

    mock_module.pipeline = mock_pipeline_fn

    with patch.dict("sys.modules", {"transformers": mock_module}):
        yield mock_pipeline_fn


async def _make_detector(
    config: dict[str, Any] | None = None,
) -> ToxicityDetector:
    """Create and initialize a ToxicityDetector for testing."""
    detector = ToxicityDetector()
    await detector.initialize(config or {})
    return detector


# --------------------------------------------------------------------------- #
# TC-TOX-001, TC-TOX-006: Model loading and detection
# --------------------------------------------------------------------------- #


class TestToxicityDetection:
    """REQ-001: Load unitary/toxic-bert and detect toxic content."""

    async def test_tc_tox_001_detects_toxic_content(self) -> None:
        """TC-TOX-001: toxic-bert model detects toxic content.

        SC-001 / SC-002: When detect() is called with content containing
        toxic language, the detector returns a DetectionResult with
        confidence reflecting the model's toxicity score and
        category='toxicity'.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.95}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("You are a stupid idiot", ctx)

        assert result.confidence == pytest.approx(0.95)
        assert result.category == "toxicity"

    async def test_tc_tox_006_uses_transformers_pipeline_cpu(self) -> None:
        """TC-TOX-006: Uses transformers pipeline with CPU inference.

        SC-001: The detector loads the model using the transformers
        pipeline API with model='unitary/toxic-bert' and device='cpu'.
        """
        with mock_transformers() as mock_pipeline_fn:
            detector = await _make_detector()
            ctx = _make_context()

            await detector.detect("some toxic content", ctx)

        # Verify pipeline was called with correct arguments.
        mock_pipeline_fn.assert_called_once()
        call_args = mock_pipeline_fn.call_args
        assert call_args[0][0] == "text-classification"
        assert call_args[1]["model"] == "unitary/toxic-bert"
        assert call_args[1]["device"] == "cpu"

    async def test_benign_content_returns_low_confidence(self) -> None:
        """SC-002: Benign content returns low confidence."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.05}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("Hello, how are you today?", ctx)

        assert result.confidence == pytest.approx(0.05)
        assert result.category == "toxicity"

    async def test_detector_is_subclass_of_detector_base(self) -> None:
        """ToxicityDetector is a subclass of Detector."""
        assert issubclass(ToxicityDetector, Detector)

    async def test_detector_has_correct_class_attributes(self) -> None:
        """Detector has correct name, category, description, version."""
        assert ToxicityDetector.name == "toxicity"
        assert ToxicityDetector.category == "toxicity"
        assert isinstance(ToxicityDetector.description, str)
        assert len(ToxicityDetector.description) > 0
        assert isinstance(ToxicityDetector.version, str)
        assert len(ToxicityDetector.version) > 0


# --------------------------------------------------------------------------- #
# TC-TOX-002, TC-TOX-003: Lazy loading
# --------------------------------------------------------------------------- #


class TestToxicityLazyLoading:
    """REQ-002: Model loaded on first detect(), not initialize()."""

    async def test_tc_tox_002_initialize_does_not_load_model(self) -> None:
        """TC-TOX-002: initialize() does NOT load the model.

        SC-003: initialize() only stores configuration; the model remains
        unloaded until the first detect() call.
        """
        detector = ToxicityDetector()
        assert detector._pipeline is None

        await detector.initialize({"model_name": "unitary/toxic-bert"})

        # Model should still be None after initialize.
        assert detector._pipeline is None

    async def test_tc_tox_003_first_detect_loads_subsequent_reuse(self) -> None:
        """TC-TOX-003: First detect() triggers loading; subsequent reuse.

        SC-004: The first detect() call loads the model; subsequent calls
        reuse the already-loaded model without reloading.
        """
        with mock_transformers() as mock_pipeline_fn:
            detector = await _make_detector()
            ctx = _make_context()

            # First detect — should load the model.
            await detector.detect("first content", ctx)
            assert detector._pipeline is not None
            assert mock_pipeline_fn.call_count == 1

            # Second detect — should reuse the loaded model.
            await detector.detect("second content", ctx)
            assert mock_pipeline_fn.call_count == 1  # Still only one load

            # Third detect — still no reload.
            await detector.detect("third content", ctx)
            assert mock_pipeline_fn.call_count == 1


# --------------------------------------------------------------------------- #
# TC-TOX-004, TC-TOX-005, TC-TOX-010: Threshold-driven decision
# --------------------------------------------------------------------------- #


class TestToxicityThreshold:
    """REQ-005: Threshold-driven decision (tested via ThresholdDecisionEngine)."""

    async def test_tc_tox_004_block_threshold_decision(self) -> None:
        """TC-TOX-004: confidence >= 0.90 → block.

        SC-010: When detect() returns confidence >= 0.90, the pipeline
        engine determines action='block'.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.95}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.confidence >= _BLOCK_THRESHOLD

        action = ThresholdDecisionEngine.decide(
            result.confidence, _BLOCK_THRESHOLD, _FLAG_THRESHOLD
        )
        assert action == "block"

    async def test_tc_tox_005_flag_threshold_decision(self) -> None:
        """TC-TOX-005: 0.60 <= confidence < 0.90 → flag.

        SC-011: When detect() returns confidence where 0.60 <= confidence
        < 0.90, the pipeline engine determines action='flag'.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.75}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("mildly toxic content", ctx)

        assert _FLAG_THRESHOLD <= result.confidence < _BLOCK_THRESHOLD

        action = ThresholdDecisionEngine.decide(
            result.confidence, _BLOCK_THRESHOLD, _FLAG_THRESHOLD
        )
        assert action == "flag"

    async def test_tc_tox_010_allow_threshold_decision(self) -> None:
        """TC-TOX-010: confidence < 0.60 → allow.

        SC-012: When detect() returns confidence < 0.60, the pipeline
        engine determines action='allow'.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.30}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("mostly benign content", ctx)

        assert result.confidence < _FLAG_THRESHOLD

        action = ThresholdDecisionEngine.decide(
            result.confidence, _BLOCK_THRESHOLD, _FLAG_THRESHOLD
        )
        assert action == "allow"

    async def test_detector_does_not_hardcode_action(self) -> None:
        """SC-010: The detector only computes confidence, not the final action.

        The detector returns a placeholder action ('allow'); the pipeline
        engine overrides it using ThresholdDecisionEngine.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.95}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        # Detector returns a placeholder action, not 'block'.
        assert result.action == "allow"
        # But confidence is high enough for the engine to decide 'block'.
        assert result.confidence >= _BLOCK_THRESHOLD


# --------------------------------------------------------------------------- #
# TC-TOX-007, TC-TOX-008, TC-TOX-015: Offline mode
# --------------------------------------------------------------------------- #


class TestToxicityOfflineMode:
    """REQ-003: Support offline_mode."""

    async def test_tc_tox_007_offline_mode_loads_from_cache(self) -> None:
        """TC-TOX-007: offline_mode=true loads from local cache, no network.

        SC-005: When offline_mode=true and the model is cached, the
        detector loads from cache without making network requests.
        """
        # Start with a clean environment (no HF_HUB_OFFLINE set).
        with (
            mock_transformers() as mock_pipeline_fn,
            patch.dict("os.environ", {}, clear=False),
        ):
            os.environ.pop("HF_HUB_OFFLINE", None)

            detector = await _make_detector({"offline_mode": True})
            ctx = _make_context()

            await detector.detect("toxic content", ctx)

            # Verify HF_HUB_OFFLINE was set to "1" (inside patch.dict
            # so the env change is visible before restoration).
            assert os.environ.get("HF_HUB_OFFLINE") == "1"

        # Verify pipeline was still called (model loaded from cache).
        mock_pipeline_fn.assert_called_once()

        # Cleanup.
        os.environ.pop("HF_HUB_OFFLINE", None)

    async def test_tc_tox_008_offline_model_not_cached_fails(self) -> None:
        """TC-TOX-008: offline_mode=true, model not cached → fails.

        SC-006: When offline_mode=true and the model is NOT cached, the
        detector fails to load and the error is handled by on_error.
        """
        load_error = OSError("Model not found in offline cache")

        with mock_transformers(side_effect=load_error):
            detector = await _make_detector(
                {"offline_mode": True, "on_error": "fail_open"}
            )
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.error is not None
        assert "Model not found in offline cache" in result.error
        assert result.action == "allow"
        assert result.confidence == 0.0

        # Cleanup.
        os.environ.pop("HF_HUB_OFFLINE", None)

    async def test_tc_tox_015_offline_false_downloads_from_hub(self) -> None:
        """TC-TOX-015: offline_mode=false downloads from HuggingFace Hub.

        SC-007: When offline_mode=false (default), the detector downloads
        the model from HuggingFace Hub if not cached.
        """
        # Start with a clean environment.
        with (
            mock_transformers() as mock_pipeline_fn,
            patch.dict("os.environ", {}, clear=False),
        ):
            os.environ.pop("HF_HUB_OFFLINE", None)

            detector = await _make_detector({"offline_mode": False})
            ctx = _make_context()

            await detector.detect("toxic content", ctx)

            # HF_HUB_OFFLINE should NOT be set when offline_mode=False.
            assert os.environ.get("HF_HUB_OFFLINE") != "1"

        # Pipeline was called (model loaded/downloaded).
        mock_pipeline_fn.assert_called_once()

        # Cleanup.
        os.environ.pop("HF_HUB_OFFLINE", None)


# --------------------------------------------------------------------------- #
# TC-TOX-009, TC-TOX-016: Config overrides
# --------------------------------------------------------------------------- #


class TestToxicityConfig:
    """REQ-004: Support model_cache_dir and model_version config."""

    async def test_tc_tox_009_cache_dir_and_version_take_effect(self) -> None:
        """TC-TOX-009: model_cache_dir and model_version override globals.

        SC-008: When configured, model_cache_dir is passed as cache_dir
        and model_version is passed as revision to the pipeline.
        """
        with mock_transformers() as mock_pipeline_fn:
            detector = await _make_detector(
                {
                    "model_cache_dir": "/app/models",
                    "model_version": "v1.0",
                }
            )
            ctx = _make_context()

            await detector.detect("toxic content", ctx)

        call_kwargs = mock_pipeline_fn.call_args[1]
        assert call_kwargs["cache_dir"] == "/app/models"
        assert call_kwargs["revision"] == "v1.0"

    async def test_tc_tox_016_defaults_latest_and_global_cache(self) -> None:
        """TC-TOX-016: Default model_version uses latest, cache_dir global.

        SC-009: When model_version and model_cache_dir are omitted, the
        detector uses the latest revision and the global cache dir (i.e.,
        neither revision nor cache_dir is passed to the pipeline).
        """
        with mock_transformers() as mock_pipeline_fn:
            detector = await _make_detector()
            ctx = _make_context()

            await detector.detect("toxic content", ctx)

        call_kwargs = mock_pipeline_fn.call_args[1]
        # revision and cache_dir should NOT be in kwargs when not configured.
        assert "revision" not in call_kwargs
        assert "cache_dir" not in call_kwargs

    async def test_custom_model_name_is_used(self) -> None:
        """Custom model_name is passed to the pipeline."""
        with mock_transformers() as mock_pipeline_fn:
            detector = await _make_detector(
                {"model_name": "custom/toxic-model"}
            )
            ctx = _make_context()

            await detector.detect("toxic content", ctx)

        call_kwargs = mock_pipeline_fn.call_args[1]
        assert call_kwargs["model"] == "custom/toxic-model"

    async def test_custom_thresholds_stored(self) -> None:
        """Custom thresholds are stored during initialize()."""
        detector = await _make_detector(
            {
                "block_threshold": 0.80,
                "flag_threshold": 0.50,
            }
        )
        assert detector._block_threshold == 0.80
        assert detector._flag_threshold == 0.50


# --------------------------------------------------------------------------- #
# TC-TOX-012, TC-TOX-013: Error handling (on_error strategy)
# --------------------------------------------------------------------------- #


class TestToxicityErrorHandling:
    """REQ-007: Model loading failure handled by on_error strategy."""

    async def test_tc_tox_012_fail_open_model_load_fails(self) -> None:
        """TC-TOX-012: on_error=fail_open, model load fails → action=allow.

        SC-014: When on_error='fail_open' and model loading fails, the
        detector returns action='allow' with confidence=0.0 and the error
        message in the result.
        """
        load_error = RuntimeError("Connection refused")

        with mock_transformers(side_effect=load_error):
            detector = await _make_detector({"on_error": "fail_open"})
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.action == "allow"
        assert result.confidence == 0.0
        assert result.error is not None
        assert "Connection refused" in result.error
        assert result.risk_level == "low"

    async def test_tc_tox_013_fail_closed_model_load_fails(self) -> None:
        """TC-TOX-013: on_error=fail_closed, model load fails → action=block.

        SC-015: When on_error='fail_closed' and model loading fails, the
        detector returns action='block' with the error message in the
        result.
        """
        load_error = RuntimeError("Connection refused")

        with mock_transformers(side_effect=load_error):
            detector = await _make_detector({"on_error": "fail_closed"})
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.action == "block"
        assert result.error is not None
        assert "Connection refused" in result.error

    async def test_default_on_error_is_fail_open(self) -> None:
        """Default on_error strategy is 'fail_open'."""
        detector = await _make_detector()
        assert detector._on_error == "fail_open"

    async def test_error_result_has_correct_category(self) -> None:
        """Error result still has category='toxicity'."""
        load_error = RuntimeError("test error")

        with mock_transformers(side_effect=load_error):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.category == "toxicity"
        assert result.detector_name == "toxicity"

    async def test_error_result_details_show_model_not_loaded(self) -> None:
        """Error result details show model_loaded=False."""
        load_error = RuntimeError("test error")

        with mock_transformers(side_effect=load_error):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.details.get("model_loaded") is False


# --------------------------------------------------------------------------- #
# TC-TOX-011, TC-TOX-014: Result fields and initialize behavior
# --------------------------------------------------------------------------- #


class TestToxicityResult:
    """REQ-006 / REQ-008: DetectionResult fields and initialize behavior."""

    async def test_tc_tox_011_result_has_correct_fields(self) -> None:
        """TC-TOX-011: DetectionResult has correct fields.

        SC-013: category='toxicity', detector_name='toxicity', confidence
        (float 0.0-1.0), risk_level, message.
        """
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.85}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert isinstance(result, DetectionResult)
        assert result.detector_name == "toxicity"
        assert result.category == "toxicity"
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        assert result.risk_level in ("low", "medium", "high", "critical")
        assert isinstance(result.message, str)
        assert len(result.message) > 0

    async def test_result_risk_level_critical_for_high_confidence(self) -> None:
        """risk_level='critical' when confidence >= 0.90."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.95}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.confidence >= 0.90
        assert result.risk_level == "critical"

    async def test_result_risk_level_high_for_medium_confidence(self) -> None:
        """risk_level='high' when 0.60 <= confidence < 0.90."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.75}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert 0.60 <= result.confidence < 0.90
        assert result.risk_level == "high"

    async def test_result_risk_level_medium_for_low_confidence(self) -> None:
        """risk_level='medium' when 0 < confidence < 0.60."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.30}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert 0 < result.confidence < 0.60
        assert result.risk_level == "medium"

    async def test_result_risk_level_low_for_zero_confidence(self) -> None:
        """risk_level='low' when confidence = 0.0."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.0}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("benign content", ctx)

        assert result.confidence == 0.0
        assert result.risk_level == "low"

    async def test_result_details_contain_model_info(self) -> None:
        """Details contain model name, toxicity_score, and model_loaded."""
        with mock_transformers(
            return_value=[{"label": "toxic", "score": 0.92}]
        ):
            detector = await _make_detector()
            ctx = _make_context()

            result = await detector.detect("toxic content", ctx)

        assert result.details["model"] == "unitary/toxic-bert"
        assert result.details["toxicity_score"] == pytest.approx(0.92)
        assert result.details["model_loaded"] is True

    async def test_tc_tox_014_initialize_only_stores_config(self) -> None:
        """TC-TOX-014: initialize() only stores config, no model loading.

        SC-016: initialize() stores model_name, model_cache_dir,
        offline_mode, and thresholds. It does NOT load the model or make
        network requests.
        """
        config: dict[str, Any] = {
            "model_name": "unitary/toxic-bert",
            "model_cache_dir": "/app/models",
            "model_version": "v1.0",
            "offline_mode": True,
            "on_error": "fail_closed",
            "block_threshold": 0.85,
            "flag_threshold": 0.50,
        }

        detector = ToxicityDetector()
        await detector.initialize(config)

        # All config values should be stored.
        assert detector._model_name == "unitary/toxic-bert"
        assert detector._model_cache_dir == "/app/models"
        assert detector._model_version == "v1.0"
        assert detector._offline_mode is True
        assert detector._on_error == "fail_closed"
        assert detector._block_threshold == 0.85
        assert detector._flag_threshold == 0.50

        # Model should NOT be loaded.
        assert detector._pipeline is None

    async def test_initialize_with_empty_config_uses_defaults(self) -> None:
        """initialize() with empty config uses all default values."""
        detector = ToxicityDetector()
        await detector.initialize({})

        assert detector._model_name == "unitary/toxic-bert"
        assert detector._model_cache_dir is None
        assert detector._model_version is None
        assert detector._offline_mode is False
        assert detector._on_error == "fail_open"
        assert detector._block_threshold == 0.90
        assert detector._flag_threshold == 0.60
        assert detector._pipeline is None

    async def test_health_check_returns_true_when_initialized(self) -> None:
        """health_check() returns True after initialization."""
        detector = await _make_detector()
        assert await detector.health_check() is True

    async def test_health_check_returns_true_when_model_loaded(self) -> None:
        """health_check() returns True after model is loaded."""
        with mock_transformers():
            detector = await _make_detector()
            ctx = _make_context()
            await detector.detect("content", ctx)

            assert await detector.health_check() is True
