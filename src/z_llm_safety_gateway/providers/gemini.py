"""Google Gemini generateContent adapter with OpenAI-compatible responses."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from z_llm_safety_gateway.providers.base import BaseProvider, ProviderError


class GeminiProvider(BaseProvider):
    """Translate the gateway chat contract to Gemini's generateContent API."""

    def _build_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {
            **headers,
            "Content-Type": "application/json",
            "x-goog-api-key": self.config.api_key,
        }

    @staticmethod
    def _request(request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        model = str(request.get("model", ""))
        if not model:
            raise ProviderError("gemini", "Model is required")
        contents: list[dict[str, Any]] = []
        system: Any | None = request.get("system")
        for message in request.get("messages", []):
            role = message.get("role")
            if role == "system":
                system = message.get("content", "")
                continue
            if role == "tool":
                tool_name = message.get("name")
                if not isinstance(tool_name, str) or not tool_name:
                    raise ProviderError("gemini", "Tool result is missing name")
                try:
                    result = json.loads(str(message.get("content", "{}")))
                except json.JSONDecodeError:
                    result = {"content": str(message.get("content", ""))}
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {"functionResponse": {"name": tool_name, "response": result}}
                        ],
                    }
                )
                continue
            if role not in {"user", "assistant"}:
                raise ProviderError("gemini", "Unsupported message role")
            content = message.get("content", "")
            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list) and all(
                isinstance(part, dict) and part.get("type") == "text" for part in content
            ):
                parts = [{"text": str(part.get("text", ""))} for part in content]
            else:
                raise ProviderError("gemini", "Unsupported message content")
            contents.append({"role": "model" if role == "assistant" else "user", "parts": parts})
        body: dict[str, Any] = {"contents": contents}
        if system is not None:
            body["systemInstruction"] = {"parts": [{"text": str(system)}]}
        generation: dict[str, Any] = {}
        for source, target in (
            ("temperature", "temperature"),
            ("top_p", "topP"),
            ("max_tokens", "maxOutputTokens"),
        ):
            if source in request:
                generation[target] = request[source]
        if generation:
            body["generationConfig"] = generation
        if "tools" in request:
            declarations: list[dict[str, Any]] = []
            for tool in request["tools"]:
                function = tool.get("function") if isinstance(tool, dict) else None
                if tool.get("type") != "function" or not isinstance(function, dict):
                    raise ProviderError("gemini", "Unsupported tool definition")
                declarations.append(
                    {
                        "name": function.get("name", ""),
                        "description": function.get("description", ""),
                        "parameters": function.get("parameters", {}),
                    }
                )
            body["tools"] = [{"functionDeclarations": declarations}]
        if "tool_choice" in request:
            choice = request["tool_choice"]
            config: dict[str, Any]
            if choice == "auto":
                config = {"mode": "AUTO"}
            elif choice == "required":
                config = {"mode": "ANY"}
            elif choice == "none":
                config = {"mode": "NONE"}
            elif isinstance(choice, dict) and choice.get("type") == "function":
                config = {
                    "mode": "ANY",
                    "allowedFunctionNames": [choice.get("function", {}).get("name", "")],
                }
            else:
                raise ProviderError("gemini", "Unsupported tool_choice")
            body["toolConfig"] = {"functionCallingConfig": config}
        return model, body

    def _build_url_for(self, model: str, *, stream: bool = False) -> str:
        suffix = ":streamGenerateContent?alt=sse" if stream else ":generateContent"
        return f"{self.config.base_url.rstrip('/')}/models/{model}{suffix}"

    async def _call(
        self, model: str, body: dict[str, Any], headers: dict[str, str]
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url_for(model),
                    json=body,
                    headers=self._build_headers(headers),
                )
        except httpx.TimeoutException:
            raise ProviderError(
                self.config.name,
                f"Provider '{self.config.name}' timeout after {self.timeout}s",
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                self.config.name,
                f"Network error connecting to provider '{self.config.name}'",
            ) from None
        if response.status_code >= 400:
            raise ProviderError(
                self.config.name,
                f"Provider '{self.config.name}' returned HTTP {response.status_code}",
                response.status_code,
                response.headers.get("Retry-After"),
            )
        return response

    @staticmethod
    def _response(response: httpx.Response) -> httpx.Response:
        data = response.json()
        candidate = (data.get("candidates") or [{}])[0]
        text = "".join(
            part.get("text", "")
            for part in candidate.get("content", {}).get("parts", [])
        )
        tool_calls = [
            {
                "id": part.get("functionCall", {}).get("name", ""),
                "type": "function",
                "function": {
                    "name": part.get("functionCall", {}).get("name", ""),
                    "arguments": json.dumps(part.get("functionCall", {}).get("args", {})),
                },
            }
            for part in candidate.get("content", {}).get("parts", [])
            if "functionCall" in part
        ]
        message: dict[str, Any] = {"role": "assistant", "content": text or None}
        if tool_calls:
            message["tool_calls"] = tool_calls
        normalized = {
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": {
                        "STOP": "stop",
                        "MAX_TOKENS": "length",
                        "SAFETY": "content_filter",
                    }.get(candidate.get("finishReason"), candidate.get("finishReason")),
                }
            ],
            "usage": data.get("usageMetadata", {}),
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
        model, body = self._request(request)
        return self._response(await self._call(model, body, headers))

    async def stream_forward(
        self, request: dict[str, Any], headers: dict[str, str]
    ) -> AsyncIterator[str]:
        model, body = self._request(request)
        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout) as client,
                client.stream(
                    "POST",
                    self._build_url_for(model, stream=True),
                    json=body,
                    headers=self._build_headers(headers),
                ) as response,
            ):
                if response.status_code >= 400:
                    raise ProviderError(
                        self.config.name,
                        f"Provider '{self.config.name}' returned HTTP {response.status_code}",
                        response.status_code,
                        response.headers.get("Retry-After"),
                    )
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event, buffer = buffer.split("\n\n", 1)
                        for line in event.splitlines():
                            if not line.startswith("data:"):
                                continue
                            try:
                                data = json.loads(line[5:].strip())
                                parts = data["candidates"][0]["content"]["parts"]
                            except (ValueError, KeyError, IndexError):
                                continue
                            text = "".join(part.get("text", "") for part in parts)
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
                yield "data: [DONE]\n\n"
        except ProviderError:
            raise
        except httpx.TimeoutException:
            raise ProviderError(
                self.config.name,
                f"Provider '{self.config.name}' timeout after {self.timeout}s",
            ) from None
        except httpx.HTTPError:
            raise ProviderError(
                self.config.name,
                f"Network error connecting to provider '{self.config.name}'",
            ) from None
