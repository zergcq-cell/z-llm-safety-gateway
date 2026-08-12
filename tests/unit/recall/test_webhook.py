"""Unit tests for WebhookRecall.

Covers TC-PAR-007 and TC-PAR-008 (post-audit-recall spec).
"""

from __future__ import annotations

import asyncio

from z_llm_safety_gateway.recall.webhook import WebhookRecall


class _FakeTransport:
    """Fake httpx transport that records requests and returns responses."""

    def __init__(self, status_codes: list[int]) -> None:
        self.status_codes = status_codes
        self.calls: list[tuple[str, dict]] = []

    async def handle_async_request(self, request):
        from httpx import Response

        url = str(request.url)
        headers = dict(request.headers)
        self.calls.append((url, headers))
        code = self.status_codes[min(len(self.calls) - 1, len(self.status_codes) - 1)]
        return Response(code, request=request)


def _make_webhook(status_codes: list[int]) -> WebhookRecall:
    transport = _FakeTransport(status_codes)
    webhook = WebhookRecall(
        webhook_url="http://hooks.example.com/recall",
        webhook_auth_header="Bearer test-token",
        max_retries=3,
        backoff=(0.001, 0.002, 0.004),
        timeout=5,
        transport=transport,
    )
    # Expose the fake transport for call inspection in tests.
    webhook._fake_transport = transport
    return webhook


# --------------------------------------------------------------------------- #
# TC-PAR-007: webhook retry + backoff, 2xx success
# --------------------------------------------------------------------------- #
def test_webhook_success_on_2xx():
    """TC-PAR-007: 2xx response marks delivery successful."""
    webhook = _make_webhook([200])
    result = asyncio.run(
        webhook.send(
            request_id="req_1",
            risk_level="critical",
            reason="leak",
            category="secret",
        )
    )
    assert result.delivered is True
    assert result.attempts == 1
    assert webhook._fake_transport.calls[0][0] == "http://hooks.example.com/recall"


def test_webhook_retries_then_success():
    """TC-PAR-007b: retries after failures, succeeds on later attempt."""
    webhook = _make_webhook([500, 500, 200])
    result = asyncio.run(
        webhook.send(
            request_id="req_2",
            risk_level="high",
            reason="x",
            category="y",
        )
    )
    assert result.delivered is True
    assert result.attempts == 3


# --------------------------------------------------------------------------- #
# TC-PAR-008: all attempts fail -> recall_delivery: failed
# --------------------------------------------------------------------------- #
def test_webhook_all_fail_marks_failed():
    """TC-PAR-008: all retries fail marks delivery failed."""
    webhook = _make_webhook([500, 500, 500, 500])
    result = asyncio.run(
        webhook.send(
            request_id="req_3",
            risk_level="medium",
            reason="x",
            category="y",
        )
    )
    assert result.delivered is False
    assert result.attempts == 3


def test_webhook_auth_header_included():
    """TC-PAR-007c: auth header is included in webhook request."""
    webhook = _make_webhook([200])
    asyncio.run(webhook.send(request_id="req_4", risk_level="low", reason="x", category="y"))
    headers = webhook._fake_transport.calls[0][1]
    assert headers.get("authorization") == "Bearer test-token"
