"""OpenAI-compatible endpoint provider adapter (Ollama, vLLM, LM Studio, etc.)."""

from __future__ import annotations

from typing import Any

import httpx

from z_llm_safety_gateway.providers.base import BaseProvider


class OpenAICompatibleProvider(BaseProvider):
    """Provider adapter for any OpenAI-compatible API endpoint.

    Behaves like :class:`OpenAIProvider` but the ``api_key`` is optional.
    When an ``api_key`` is configured the ``Authorization`` header is added;
    otherwise it is omitted.  No format conversion is performed.
    """

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Merge pass-through headers; add auth only when api_key is set."""
        result: dict[str, str] = {**headers, "Content-Type": "application/json"}
        if self.config.api_key:
            result["Authorization"] = f"Bearer {self.config.api_key}"
        return result

    async def forward_request(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        """Forward *request* to the OpenAI-compatible endpoint as-is."""
        return await self._send(request, headers)
