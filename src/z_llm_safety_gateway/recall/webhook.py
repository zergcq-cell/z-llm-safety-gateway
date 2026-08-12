"""Webhook-based response recall (v0.3.0).

Implements DESIGN.md Section 8.4: when a post-audit (or async output
detection) finds a risk after the response has already been delivered, POST a
recall to a configured webhook.  Retries with exponential backoff
(1s/2s/4s), a 5s timeout per attempt, and treats any HTTP 2xx as success.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class WebhookResult:
    """Result of a webhook recall delivery.

    Attributes:
        delivered: True if any attempt returned HTTP 2xx.
        attempts: Number of attempts made (max_retries maximum).
    """

    delivered: bool = False
    attempts: int = 0


class WebhookRecall:
    """Delivers recall signals to a configured webhook with retry/backoff.

    Args:
        webhook_url: The callback URL.
        webhook_auth_header: Optional ``Authorization`` header value.
        max_retries: Maximum number of attempts (default 3).
        backoff: Tuple of backoff delays in seconds between attempts.
        timeout: Per-attempt timeout in seconds (default 5).
        transport: Optional custom httpx transport (for testing).
    """

    def __init__(
        self,
        webhook_url: str = "",
        webhook_auth_header: str = "",
        max_retries: int = 3,
        backoff: tuple[float, ...] = (1.0, 2.0, 4.0),
        timeout: float = 5.0,
        transport: Any | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._webhook_auth_header = webhook_auth_header
        self._max_retries = max_retries
        self._backoff = backoff
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout, transport=self._transport)
        return self._client

    async def send(
        self,
        request_id: str,
        risk_level: str,
        reason: str,
        category: str,
    ) -> WebhookResult:
        """Send a recall POST to the webhook with retry/backoff.

        Returns a :class:`WebhookResult`.  A successful attempt is any HTTP
        2xx status.  All attempts failing yields ``delivered: False``.
        """
        if not self._webhook_url:
            return WebhookResult(delivered=False, attempts=0)

        client = self._get_client()
        headers = {}
        if self._webhook_auth_header:
            headers["Authorization"] = self._webhook_auth_header

        payload = {
            "request_id": request_id,
            "risk_level": risk_level,
            "reason": reason,
            "category": category,
        }

        attempts = 0
        for attempt in range(self._max_retries):
            attempts += 1
            try:
                resp = await client.post(self._webhook_url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    return WebhookResult(delivered=True, attempts=attempts)
            except httpx.HTTPError:
                pass
            # Backoff between attempts (not after the last).
            if attempt < self._max_retries - 1 and attempt < len(self._backoff):
                await asyncio.sleep(self._backoff[attempt])

        return WebhookResult(delivered=False, attempts=attempts)

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
