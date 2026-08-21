"""Tests for the example AcmeKeywordDetector."""

from __future__ import annotations

import pytest
from acme_keyword_detector.detector import AcmeKeywordDetector
from z_llm_safety_gateway_sdk.testing import (
    assert_allowed,
    assert_blocked,
    make_context,
)

CONFIG = {
    "block_keywords": ["competitor-x", "layoff"],
    "redact_keywords": ["acme-secret"],
    "block_threshold": 0.85,
}


@pytest.fixture
async def detector() -> AcmeKeywordDetector:
    det = AcmeKeywordDetector()
    await det.initialize(CONFIG)
    return det


async def test_allows_safe_content(detector: AcmeKeywordDetector) -> None:
    result = await detector.detect("Hello, welcome to our product page!", make_context())
    assert_allowed(result)


async def test_blocks_disallowed_keyword(detector: AcmeKeywordDetector) -> None:
    result = await detector.detect("Our competitor-x is releasing soon", make_context())
    assert_blocked(result)
    assert result.details["matched_keyword"] == "competitor-x"
    assert result.confidence == pytest.approx(0.85)


async def test_redacts_secret_keyword(detector: AcmeKeywordDetector) -> None:
    result = await detector.detect("The code is acme-secret, do not share", make_context())
    assert result.action == "modify"
    assert result.modified_content == "The code is ***********, do not share"
