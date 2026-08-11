"""OpenAI API provider adapter."""

from __future__ import annotations

from typing import Any

import httpx

from z_llm_safety_gateway.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider adapter for the official OpenAI API.

    Forwards requests to ``{base_url}/chat/completions`` with a
    ``Bearer`` authorization header.  No request-body modification,
    no retry, and no failover (MVP).
    """

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Merge pass-through headers with provider auth (auth always wins)."""
        return {
            **headers,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    async def forward_request(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        """Forward *request* to the OpenAI chat-completions endpoint."""
        return await self._send(request, headers)
