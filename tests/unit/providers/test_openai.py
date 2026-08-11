"""Tests for OpenAIProvider — TC-PROXY-005, TC-PROXY-008 through TC-PROXY-011."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.openai import OpenAIProvider

_OPENAI_CONFIG = ProviderConfig(
    name="openai",
    type="openai",
    base_url="https://api.openai.com/v1",
    api_key="sk-test-key-12345",
)

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"

_SAMPLE_REQUEST: dict[str, object] = {
    "model": "gpt-4-turbo",
    "messages": [{"role": "user", "content": "Hello, world!"}],
}

_SAMPLE_RESPONSE: dict[str, object] = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi there!"},
            "finish_reason": "stop",
        }
    ],
}


class TestOpenAIProviderForward:
    """Tests for OpenAIProvider.forward_request() — TC-PROXY-005."""

    @respx.mock
    async def test_forward_request_forwards_to_base_url_with_auth_body_unchanged(self) -> None:
        """TC-PROXY-005: forwards request to base_url with Bearer auth, body unmodified."""
        route = respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=200, json=_SAMPLE_RESPONSE
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        response = await provider.forward_request(_SAMPLE_REQUEST, {})

        assert response.status_code == 200
        assert response.json() == _SAMPLE_RESPONSE
        assert route.called

        sent_request = route.calls[0].request
        assert sent_request.url == httpx.URL(_CHAT_COMPLETIONS_URL)
        assert sent_request.headers["Authorization"] == "Bearer sk-test-key-12345"
        sent_body = json.loads(sent_request.content)
        assert sent_body == _SAMPLE_REQUEST

    @respx.mock
    async def test_forward_request_passes_through_extra_headers(self) -> None:
        """Extra headers (e.g. X-Request-ID) are forwarded to the provider."""
        respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=200, json=_SAMPLE_RESPONSE
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        await provider.forward_request(_SAMPLE_REQUEST, {"X-Request-ID": "req-abc"})

        sent_request = respx.calls[0].request
        assert sent_request.headers["X-Request-ID"] == "req-abc"


class TestOpenAIProviderTimeout:
    """Tests for OpenAIProvider timeout handling — TC-PROXY-008."""

    @respx.mock
    async def test_forward_request_timeout_raises_provider_error(self) -> None:
        """TC-PROXY-008: provider timeout raises ProviderError with
        provider name and timeout message."""
        respx.post(_CHAT_COMPLETIONS_URL).mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        provider = OpenAIProvider(_OPENAI_CONFIG, timeout=120.0)

        with pytest.raises(ProviderError) as exc_info:
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert exc_info.value.provider_name == "openai"
        assert "timeout" in exc_info.value.message.lower()


class TestOpenAIProviderHttpError:
    """Tests for OpenAIProvider 4xx/5xx error handling — TC-PROXY-009."""

    @respx.mock
    async def test_forward_request_4xx_raises_provider_error_with_status_and_retry_after(
        self,
    ) -> None:
        """TC-PROXY-009: 4xx response raises ProviderError with status code and Retry-After."""
        respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=429,
            json={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
            headers={"Retry-After": "60"},
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        with pytest.raises(ProviderError) as exc_info:
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert exc_info.value.provider_name == "openai"
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after == "60"

    @respx.mock
    async def test_forward_request_5xx_raises_provider_error_with_status(self) -> None:
        """TC-PROXY-009: 5xx response raises ProviderError with status code and provider name."""
        respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=500,
            json={"error": {"message": "Internal server error", "type": "server_error"}},
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        with pytest.raises(ProviderError) as exc_info:
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert exc_info.value.provider_name == "openai"
        assert exc_info.value.status_code == 500

    @respx.mock
    async def test_forward_request_4xx_no_retry_after_is_none(self) -> None:
        """ProviderError.retry_after is None when no Retry-After header is present."""
        respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=400,
            json={"error": {"message": "Bad request"}},
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        with pytest.raises(ProviderError) as exc_info:
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert exc_info.value.retry_after is None
        assert exc_info.value.status_code == 400


class TestOpenAIProviderNetworkError:
    """Tests for OpenAIProvider network error handling — TC-PROXY-010."""

    @respx.mock
    async def test_forward_request_network_error_raises_provider_error(self) -> None:
        """TC-PROXY-010: network error raises ProviderError with
        provider name and generic message."""
        respx.post(_CHAT_COMPLETIONS_URL).mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        with pytest.raises(ProviderError) as exc_info:
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert exc_info.value.provider_name == "openai"
        assert "network" in exc_info.value.message.lower()


class TestOpenAIProviderNoRetry:
    """Tests for OpenAIProvider no-retry behavior — TC-PROXY-011."""

    @respx.mock
    async def test_forward_request_error_no_retry_single_attempt(self) -> None:
        """TC-PROXY-011: provider error results in single attempt, no retry."""
        route = respx.post(_CHAT_COMPLETIONS_URL).respond(
            status_code=500,
            json={"error": {"message": "Internal server error"}},
        )
        provider = OpenAIProvider(_OPENAI_CONFIG)

        with pytest.raises(ProviderError):
            await provider.forward_request(_SAMPLE_REQUEST, {})

        assert route.call_count == 1
