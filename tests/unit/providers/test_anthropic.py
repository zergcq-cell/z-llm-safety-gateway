import asyncio
import json

import httpx
import pytest
import respx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.anthropic import AnthropicProvider
from z_llm_safety_gateway.providers.base import ProviderError

CFG = ProviderConfig(
    name="claude",
    type="anthropic",
    base_url="https://api.anthropic.com/v1",
    api_key="a-key",
    api_version="2023-06-01",
)

@respx.mock
async def test_anthropic_request_and_response_are_normalized():
    route = respx.post("https://api.anthropic.com/v1/messages").respond(
        200,
        json={
            "id": "m1",
            "role": "assistant",
            "content": [{"type": "text", "text": "hi"}],
            "stop_reason": "end_turn",
        },
    )
    response = await AnthropicProvider(CFG).forward_request(
        {
            "model": "claude-3",
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello"},
            ],
            "max_tokens": 32,
        },
        {},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["messages"][0]["role"] == "user"
    assert sent["system"] == "be brief"
    assert route.calls[0].request.headers["x-api-key"] == "a-key"
    assert response.json()["choices"][0]["message"]["content"] == "hi"


@respx.mock
async def test_anthropic_stream_normalizes_text_and_done():
    respx.post("https://api.anthropic.com/v1/messages").respond(
        200,
        content=b'data: {"delta":{"text":"hi"}}\n\ndata: {"type":"message_stop"}\n\n',
        headers={"content-type": "text/event-stream"},
    )
    chunks = [
        chunk
        async for chunk in AnthropicProvider(CFG).stream_forward(
            {"model": "claude-3", "messages": []}, {}
        )
    ]
    assert '"content": "hi"' in chunks[0]
    assert chunks[-1] == "data: [DONE]\n\n"


async def test_anthropic_rejects_unsupported_content_explicitly():
    with pytest.raises(ProviderError, match="Unsupported message content block"):
        await AnthropicProvider(CFG).forward_request(
            {"model": "claude-3", "messages": [{"role": "user", "content": [{"type": "image"}]}]},
            {},
        )


@respx.mock
async def test_anthropic_translates_tool_result_and_tool_choice():
    route = respx.post("https://api.anthropic.com/v1/messages").respond(
        200,
        json={"content": [], "stop_reason": "tool_use"},
    )
    response = await AnthropicProvider(CFG).forward_request(
        {
            "model": "claude-3",
            "messages": [
                {"role": "tool", "tool_call_id": "call-1", "content": "{\"ok\": true}"}
            ],
            "tools": [
                {"type": "function", "function": {"name": "weather", "parameters": {}}}
            ],
            "tool_choice": "required",
        },
        {},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["messages"][0]["content"][0]["type"] == "tool_result"
    assert sent["tool_choice"] == {"type": "any"}
    assert response.json()["choices"][0]["finish_reason"] == "tool_calls"


@respx.mock
async def test_anthropic_rate_limit_uses_sanitized_provider_error():
    respx.post("https://api.anthropic.com/v1/messages").respond(
        429,
        json={"error": {"message": "upstream secret detail"}},
        headers={"Retry-After": "5"},
    )
    with pytest.raises(ProviderError) as error:
        await AnthropicProvider(CFG).forward_request(
            {"model": "claude-3", "messages": []}, {}
        )
    assert error.value.status_code == 429
    assert error.value.retry_after == "5"
    assert "secret detail" not in error.value.message


@respx.mock
@pytest.mark.parametrize(
    "failure", [httpx.TimeoutException("timeout"), httpx.ConnectError("offline")]
)
async def test_anthropic_network_failures_are_sanitized(failure):
    respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=failure)
    with pytest.raises(ProviderError) as error:
        await AnthropicProvider(CFG).forward_request({"model": "claude-3", "messages": []}, {})
    assert "offline" not in error.value.message
    assert "timeout" in error.value.message.lower() or "network" in error.value.message.lower()


async def test_anthropic_cancellation_propagates(monkeypatch):
    provider = AnthropicProvider(CFG)

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(provider, "_send", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await provider.forward_request({"model": "claude-3", "messages": []}, {})
