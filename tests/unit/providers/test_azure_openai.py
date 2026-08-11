"""Tests for AzureOpenAIProvider — TC-PROXY-007."""

from __future__ import annotations

import json

import respx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.azure_openai import AzureOpenAIProvider

_AZURE_CONFIG = ProviderConfig(
    name="azure",
    type="azure_openai",
    base_url="https://my-resource.openai.azure.com",
    api_key="azure-key-12345",
    api_version="2024-06-01",
)

_CHAT_COMPLETIONS_URL = "https://my-resource.openai.azure.com/chat/completions"

_SAMPLE_REQUEST: dict[str, object] = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello, Azure!"}],
}

_SAMPLE_RESPONSE: dict[str, object] = {
    "id": "chatcmpl-azure-123",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi from Azure!"},
            "finish_reason": "stop",
        }
    ],
}


class TestAzureOpenAIProviderForward:
    """Tests for AzureOpenAIProvider.forward_request() — TC-PROXY-007."""

    @respx.mock
    async def test_forward_request_forwards_with_api_version_and_auth(self) -> None:
        """TC-PROXY-007: forwards to base_url with api-version query param and Bearer auth."""
        route = respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=200, json=_SAMPLE_RESPONSE
        )
        provider = AzureOpenAIProvider(_AZURE_CONFIG)

        response = await provider.forward_request(_SAMPLE_REQUEST, {})

        assert response.status_code == 200
        assert response.json() == _SAMPLE_RESPONSE
        assert route.called

        sent_request = route.calls[0].request
        assert sent_request.url.params["api-version"] == "2024-06-01"
        assert sent_request.headers["Authorization"] == "Bearer azure-key-12345"

        sent_body = json.loads(sent_request.content)
        assert sent_body == _SAMPLE_REQUEST
