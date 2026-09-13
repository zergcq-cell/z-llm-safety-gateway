"""Anthropic Messages API adapter with OpenAI-compatible responses."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError


class AnthropicProvider(BaseProvider):
    """Translate the gateway chat contract to Anthropic's Messages API."""

    def _build_url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/messages"

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        result = {
            **headers,
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
        }
        if self.config.api_version:
            result["anthropic-version"] = self.config.api_version
        return result

    @staticmethod
    def _message_content(content: Any) -> Any:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            raise ProviderError("anthropic", "Unsupported message content")
        blocks: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "text":
                raise ProviderError("anthropic", "Unsupported message content block")
            blocks.append({"type": "text", "text": str(part.get("text", ""))})
        return blocks

    @classmethod
    def _request(cls, request: dict[str, Any]) -> dict[str, Any]:
        system = request.get("system")
        messages: list[dict[str, Any]] = []
        for message in request.get("messages", []):
            role = message.get("role")
            if role == "system":
                system = message.get("content", "")
                continue
            if role == "tool":
                tool_use_id = message.get("tool_call_id")
                if not isinstance(tool_use_id, str) or not tool_use_id:
                    raise ProviderError("anthropic", "Tool result is missing tool_call_id")
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": cls._message_content(message.get("content", "")),
                            }
                        ],
                    }
                )
                continue
            if role not in {"user", "assistant"}:
                raise ProviderError("anthropic", "Unsupported message role")
            messages.append(
                {"role": role, "content": cls._message_content(message.get("content", ""))}
            )
        body: dict[str, Any] = {
            "model": request.get("model"),
            "max_tokens": request.get("max_tokens", 1024),
            "messages": messages,
        }
        for key in ("temperature", "top_p", "top_k", "stop_sequences"):
            if key in request:
                body[key] = request[key]
        if system is not None:
            body["system"] = system
        if "tools" in request:
            tools = request["tools"]
            body["tools"] = [
                {
                    "name": tool["function"]["name"],
                    "description": tool["function"].get("description", ""),
                    "input_schema": tool["function"].get("parameters", {}),
                }
                for tool in tools
                if tool.get("type") == "function" and "function" in tool
            ]
            if len(body["tools"]) != len(tools):
                raise ProviderError("anthropic", "Unsupported tool definition")
        if "tool_choice" in request:
            choice = request["tool_choice"]
            if choice == "auto":
                body["tool_choice"] = {"type": "auto"}
            elif choice == "required":
                body["tool_choice"] = {"type": "any"}
            elif choice == "none":
                body["tool_choice"] = {"type": "none"}
            elif isinstance(choice, dict) and choice.get("type") == "function":
                function = choice.get("function", {})
                body["tool_choice"] = {"type": "tool", "name": function.get("name", "")}
            else:
                raise ProviderError("anthropic", "Unsupported tool_choice")
        return body

    @staticmethod
    def _response(response: httpx.Response) -> httpx.Response:
        data = response.json()
        text = "".join(
            part.get("text", "")
            for part in data.get("content", [])
            if part.get("type") == "text"
        )
        tool_calls = [
            {
                "id": part.get("id", ""),
                "type": "function",
                "function": {
                    "name": part.get("name", ""),
                    "arguments": json.dumps(part.get("input", {})),
                },
            }
            for part in data.get("content", [])
            if part.get("type") == "tool_use"
        ]
        message: dict[str, Any] = {"role": "assistant", "content": text or None}
        if tool_calls:
            message["tool_calls"] = tool_calls
        normalized = {
            "id": data.get("id", ""),
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": {
                        "end_turn": "stop",
                        "max_tokens": "length",
                        "tool_use": "tool_calls",
                    }.get(data.get("stop_reason"), data.get("stop_reason")),
                }
            ],
            "usage": data.get("usage", {}),
        }
        return httpx.Response(
            response.status_code,
            json=normalized,
            headers=response.headers,
            request=response.request,
        )

    async def forward_request(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        return self._response(await self._send(self._request(request), headers))

    async def stream_forward(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> AsyncIterator[str]:
        buffer = ""
        ended = False
        async for chunk in super().stream_forward(
            {**self._request(request), "stream": True}, headers
        ):
            buffer += chunk
            while "\n\n" in buffer:
                event, buffer = buffer.split("\n\n", 1)
                for line in event.splitlines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        ended = True
                        yield "data: [DONE]\n\n"
                        continue
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if data.get("type") == "message_stop":
                        ended = True
                        yield "data: [DONE]\n\n"
                        continue
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        normalized = {
                            "object": "chat.completion.chunk",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": text},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(normalized)}\n\n"
        if not ended:
            yield "data: [DONE]\n\n"
