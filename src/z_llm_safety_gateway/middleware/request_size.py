"""Request size limiting middleware (v0.4.0).

Implements DESIGN.md Section 11.4 / decision 4: rejects requests whose body
exceeds ``security.max_request_size`` (default ``"10MB"``) with HTTP 413 and
an OpenAI-compatible error body.

Two enforcement paths:
- When a ``Content-Length`` header is present it is checked eagerly, and the
  request is rejected before it reaches the application (TC-RSL-001).
- When the request uses chunked transfer (no ``Content-Length``) the body is
  counted as it is read and the request is interrupted with 413 as soon as the
  cumulative byte count exceeds the limit, avoiding buffering the full body
  into memory (TC-RSL-002).

This is implemented as a pure ASGI middleware (rather than
``BaseHTTPMiddleware``) so that the ``receive`` channel can be wrapped with a
byte counter; raising on the wrapped ``receive`` propagates out of the inner
application and is converted to a 413 response by this middleware.
"""

from __future__ import annotations

import json

import structlog
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from z_llm_safety_gateway.exceptions import OpenAIErrorBody, OpenAIErrorDetail
from z_llm_safety_gateway.streaming.memory import SizeLimit

logger = structlog.get_logger(__name__)

#: OpenAI-compatible error ``type``/``code`` used for 413 responses.
_ERROR_TYPE = "invalid_request_error"
_ERROR_CODE = "request_too_large"


class RequestTooLargeError(Exception):
    """Raised internally when a chunked body exceeds the configured limit.

    Attributes:
        received: Number of body bytes received so far.
        limit: The configured maximum request size in bytes.
    """

    def __init__(self, received: int, limit: int) -> None:
        self.received = received
        self.limit = limit
        super().__init__(f"Request body too large: {received} > {limit} bytes")


class RequestSizeMiddleware:
    """Reject requests whose body exceeds the configured maximum size.

    Args:
        app: The downstream ASGI application.
        max_request_size: Byte-based size limit (e.g. ``"10MB"``).
    """

    def __init__(self, app: ASGIApp, max_request_size: str = "10MB") -> None:
        self.app = app
        self._max_bytes = SizeLimit.parse(max_request_size)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. Eager Content-Length check (when the header is present).
        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = -1
            if length > self._max_bytes:
                logger.warning(
                    "request_rejected_too_large",
                    content_length=length,
                    max_request_size=self._max_bytes,
                )
                await self._send_413(send)
                return

        # 2. Read-time limit for chunked (no Content-Length) bodies.
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self._max_bytes:
                    raise RequestTooLargeError(received, self._max_bytes)
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLargeError as exc:
            logger.warning(
                "request_rejected_too_large",
                received=exc.received,
                max_request_size=exc.limit,
            )
            await self._send_413(send)

    async def _send_413(self, send: Send) -> None:
        """Send a 413 OpenAI-compatible error response."""
        body = OpenAIErrorBody(
            error=OpenAIErrorDetail(
                message="Request body too large",
                type=_ERROR_TYPE,
                code=_ERROR_CODE,
            )
        )
        content = json.dumps(body.model_dump(), ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(content)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": content})
