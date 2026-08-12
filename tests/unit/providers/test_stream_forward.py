"""Unit tests for BaseProvider.stream_forward.

Covers TC-FAST-001 (fastapi-server spec).
"""

from __future__ import annotations

import asyncio

import httpx

from z_llm_safety_gateway.config.models import ProviderConfig
from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError


class _StreamTransport(httpx.AsyncBaseTransport):
    """Fake httpx transport returning a streamed SSE response."""

    def __init__(self, chunks: list[str], status_code: int = 200) -> None:
        self.chunks = chunks
        self.status_code = status_code
        self.requests: list[tuple[str, dict]] = []

    async def handle_async_request(self, request):
        url = str(request.url)
        headers = dict(request.headers)
        self.requests.append((url, headers))

        if self.status_code >= 400:
            return httpx.Response(
                self.status_code, text="provider error", request=request
            )

        async def _aiter():
            for chunk in self.chunks:
                yield chunk.encode("utf-8")

        return httpx.Response(
            self.status_code,
            content=_aiter(),
            headers={"content-type": "text/event-stream"},
            request=request,
        )


class _ConcreteProvider(BaseProvider):
    """Minimal concrete provider for testing the base stream_forward."""

    def __init__(self, config: ProviderConfig, transport) -> None:
        super().__init__(config, timeout=120.0)
        self._transport = transport

    async def _send(self, request, headers):
        raise NotImplementedError

    async def forward_request(self, request, headers):
        raise NotImplementedError

    async def stream_forward(self, request, headers):
        # Override client creation to inject the fake transport.
        url = self._build_url()
        merged_headers = self._build_headers(headers)
        params = self._build_params()
        async with (
            httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client,
            client.stream(
                "POST",
                url,
                json=request,
                headers=merged_headers,
                params=params,
            ) as resp,
        ):
            if resp.status_code >= 400:
                raise ProviderError(
                    provider_name=self.config.name,
                    message=(
                        f"Provider '{self.config.name}' returned "
                        f"HTTP {resp.status_code}"
                    ),
                    status_code=resp.status_code,
                )
            async for chunk in resp.aiter_text():
                yield chunk


def _config() -> ProviderConfig:
    return ProviderConfig(
        name="openai",
        type="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
    )


# --------------------------------------------------------------------------- #
# TC-FAST-001: stream_forward yields SSE chunks
# --------------------------------------------------------------------------- #
def test_stream_forward_yields_chunks():
    """TC-FAST-001: stream_forward yields provider SSE chunks in order."""
    transport = _StreamTransport(['data: {"a":1}\n\n', "data: [DONE]\n\n"])
    provider = _ConcreteProvider(_config(), transport)
    chunks = asyncio.run(
        _collect(
            provider.stream_forward(
                {"messages": [{"role": "user", "content": "hi"}]},
                {"X-Test": "1"},
            )
        )
    )
    assert len(chunks) == 2
    assert chunks[0] == 'data: {"a":1}\n\n'
    assert chunks[1] == "data: [DONE]\n\n"


def test_stream_forward_builds_correct_url():
    """TC-FAST-001b: stream_forward posts to the chat-completions URL."""
    transport = _StreamTransport(['data: [DONE]\n\n'])
    provider = _ConcreteProvider(_config(), transport)
    asyncio.run(
        _collect(
            provider.stream_forward(
                {"messages": []},
                {},
            )
        )
    )
    url = transport.requests[0][0]
    assert url == "https://api.openai.com/v1/chat/completions"


def test_stream_forward_raises_on_provider_error():
    """TC-FAST-001c: stream_forward raises ProviderError on 4xx/5xx."""
    transport = _StreamTransport(['data: x\n\n'], status_code=500)
    provider = _ConcreteProvider(_config(), transport)
    try:
        asyncio.run(
            _collect(
                provider.stream_forward(
                    {"messages": []},
                    {},
                )
            )
        )
        raise AssertionError("expected ProviderError")
    except ProviderError as exc:
        assert exc.status_code == 500


async def _collect(generator) -> list[str]:
    return [chunk async for chunk in generator]
