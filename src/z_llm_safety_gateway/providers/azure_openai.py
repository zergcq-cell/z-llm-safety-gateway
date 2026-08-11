"""Azure OpenAI Service provider adapter."""

from __future__ import annotations

from typing import Any

import httpx

from z_llm_safety_gateway.providers.base import BaseProvider


class AzureOpenAIProvider(BaseProvider):
    """Provider adapter for Azure OpenAI Service.

    Forwards requests to ``{base_url}/chat/completions`` with a
    ``Bearer`` authorization header and an ``api-version`` query parameter
    taken from the provider configuration.
    """

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Merge pass-through headers with provider auth (auth always wins)."""
        return {
            **headers,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _build_params(self) -> dict[str, str] | None:
        """Add ``api-version`` query parameter when configured."""
        if self.config.api_version:
            return {"api-version": self.config.api_version}
        return None

    async def forward_request(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        """Forward *request* to the Azure OpenAI endpoint with api-version."""
        return await self._send(request, headers)
