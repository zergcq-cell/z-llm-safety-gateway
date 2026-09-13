import asyncio
import json

import httpx
import pytest
import respx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.base import ProviderError
from z_llm_safety_gateway.providers.gemini import GeminiProvider

CFG = ProviderConfig(
    name="gemini",
    type="gemini",
    base_url="https://generativelanguage.googleapis.com/v1beta",
    api_key="g-key",
)

@respx.mock
async def test_gemini_request_and_response_are_normalized():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent"
    ).respond(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": "hello"}], "role": "model"}, "finishReason": "STOP"}
            ]
        },
    )
    response = await GeminiProvider(CFG).forward_request(
        {
            "model": "gemini-1.5",
            "messages": [
                {"role": "system", "content": "brief"},
                {"role": "user", "content": "hi"},
            ],
        },
        {},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["contents"][0]["role"] == "user"
    assert sent["systemInstruction"]["parts"][0]["text"] == "brief"
    assert route.calls[0].request.headers["x-goog-api-key"] == "g-key"
    assert response.json()["choices"][0]["message"]["content"] == "hello"


@respx.mock
async def test_gemini_stream_normalizes_fragmented_sse_events():
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:streamGenerateContent?alt=sse"
    ).respond(
        200,
        content=(
            b'data: {"candidates":[{"content":{"parts":[{"text":"hel"}]}}]}\n\n'
            b'data: {"candidates":[{"content":{"parts":[{"text":"lo"}]}}]}\n\n'
        ),
        headers={"content-type": "text/event-stream"},
    )
    chunks = [
        chunk
        async for chunk in GeminiProvider(CFG).stream_forward(
            {"model": "gemini-1.5", "messages": []}, {}
        )
    ]
    assert '"content": "hel"' in chunks[0]
    assert '"content": "lo"' in chunks[1]
    assert chunks[-1] == "data: [DONE]\n\n"


@respx.mock
async def test_gemini_translates_function_tools_and_calls():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent"
    ).respond(
        200,
        json={
            "candidates": [
                {
                    "content": {
                        "parts": [{"functionCall": {"name": "weather", "args": {"city": "Paris"}}}]
                    }
                }
            ]
        },
    )
    response = await GeminiProvider(CFG).forward_request(
        {
            "model": "gemini-1.5",
            "messages": [],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "weather", "parameters": {"type": "object"}},
                }
            ],
        },
        {},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["tools"][0]["functionDeclarations"][0]["name"] == "weather"
    tool_call = response.json()["choices"][0]["message"]["tool_calls"][0]
    assert tool_call["function"]["name"] == "weather"


@respx.mock
async def test_gemini_translates_tool_result_and_specific_tool_choice():
    route = respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent"
    ).respond(200, json={"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]})
    response = await GeminiProvider(CFG).forward_request(
        {
            "model": "gemini-1.5",
            "messages": [{"role": "tool", "name": "weather", "content": "{\"temp\": 20}"}],
            "tool_choice": {"type": "function", "function": {"name": "weather"}},
        },
        {},
    )
    sent = json.loads(route.calls[0].request.content)
    assert sent["contents"][0]["parts"][0]["functionResponse"]["name"] == "weather"
    assert sent["toolConfig"]["functionCallingConfig"]["allowedFunctionNames"] == ["weather"]
    assert response.json()["choices"][0]["finish_reason"] == "length"


@respx.mock
async def test_gemini_rate_limit_uses_sanitized_provider_error():
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent"
    ).respond(429, json={"error": {"message": "upstream secret detail"}})
    with pytest.raises(ProviderError) as error:
        await GeminiProvider(CFG).forward_request(
            {"model": "gemini-1.5", "messages": []}, {}
        )
    assert error.value.status_code == 429
    assert "secret detail" not in error.value.message


@respx.mock
@pytest.mark.parametrize(
    "failure", [httpx.TimeoutException("timeout"), httpx.ConnectError("offline")]
)
async def test_gemini_network_failures_are_sanitized(failure):
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5:generateContent"
    ).mock(side_effect=failure)
    with pytest.raises(ProviderError) as error:
        await GeminiProvider(CFG).forward_request({"model": "gemini-1.5", "messages": []}, {})
    assert "offline" not in error.value.message
    assert "timeout" in error.value.message.lower() or "network" in error.value.message.lower()


async def test_gemini_cancellation_propagates(monkeypatch):
    provider = GeminiProvider(CFG)

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(provider, "_call", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await provider.forward_request({"model": "gemini-1.5", "messages": []}, {})
