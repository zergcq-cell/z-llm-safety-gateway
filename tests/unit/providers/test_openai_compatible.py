"""Tests for OpenAICompatibleProvider — TC-PROXY-006."""

from __future__ import annotations

import json

import respx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.openai_compatible import OpenAICompatibleProvider

_COMPATIBLE_CONFIG_NO_KEY = ProviderConfig(
    name="local_llama",
    type="openai_compatible",
    base_url="http://localhost:11434/v1",
)

_COMPATIBLE_CONFIG_WITH_KEY = ProviderConfig(
    name="vllm",
    type="openai_compatible",
    base_url="http://localhost:8080/v1",
    api_key="sk-local-key",
)

_CHAT_COMPLETIONS_URL_NO_KEY = "http://localhost:11434/v1/chat/completions"
_CHAT_COMPLETIONS_URL_WITH_KEY = "http://localhost:8080/v1/chat/completions"

_SAMPLE_REQUEST: dict[str, object] = {
    "model": "llama3-70b",
    "messages": [{"role": "user", "content": "Hello, world!"}],
}

_SAMPLE_RESPONSE: dict[str, object] = {
    "id": "chatcmpl-local-123",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi from local LLaMA!"},
            "finish_reason": "stop",
        }
    ],
}


class TestOpenAICompatibleProviderForward:
    """Tests for OpenAICompatibleProvider.forward_request() — TC-PROXY-006."""

    @respx.mock
    async def test_forward_request_no_api_key_forwards_without_auth_body_unchanged(self) -> None:
        """TC-PROXY-006: forwards to base_url without auth header,
        body unmodified, response as-is."""
        route = respx.post(_CHAT_COMPLETIONS_URL_NO_KEY).respond(
            status_code=200, json=_SAMPLE_RESPONSE
        )
        provider = OpenAICompatibleProvider(_COMPATIBLE_CONFIG_NO_KEY)

        response = await provider.forward_request(_SAMPLE_REQUEST, {})

        assert response.status_code == 200
        assert response.json() == _SAMPLE_RESPONSE
        assert route.called

        sent_request = route.calls[0].request
        assert "Authorization" not in sent_request.headers
        sent_body = json.loads(sent_request.content)
        assert sent_body == _SAMPLE_REQUEST

    @respx.mock
    async def test_forward_request_with_api_key_adds_auth_header(self) -> None:
        """OpenAI-compatible provider with api_key configured adds Authorization header."""
        route = respx.post(_CHAT_COMPLETIONS_URL_WITH_KEY).respond(
            status_code=200, json=_SAMPLE_RESPONSE
        )
        provider = OpenAICompatibleProvider(_COMPATIBLE_CONFIG_WITH_KEY)

        response = await provider.forward_request(_SAMPLE_REQUEST, {})

        assert response.status_code == 200
        assert route.called

        sent_request = route.calls[0].request
        assert sent_request.headers["Authorization"] == "Bearer sk-local-key"
