"""Request ID middleware — propagates or generates a UUID v4 request ID.

Checks the configured header (default: X-Request-ID) from the client:
- If ``generate`` is True and the header is present and valid
  (matches ^[a-zA-Z0-9_-]{1,128}$), uses the client value.
- If ``generate`` is False, always generates a UUID v4 (ignores client ID).
- If absent, empty, or invalid, generates a UUID v4.

Stores the request ID in request.state.request_id for downstream use and
injects the header into the response.

v0.4.0 (B-12): the header name and generate flag are now configurable via
``security.request_id.header`` and ``security.request_id.generate``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Valid client-provided request ID pattern: alphanumeric, underscore, hyphen.
REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

# UUID v4 format pattern for validation.
UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that propagates or generates a request ID for each request.

    Args:
        header_name: The header name to read/write the request ID
            (default: ``"X-Request-ID"``).
        generate: If True (default), accept a valid client-provided request
            ID; if False, always generate a UUID v4 regardless of client input.
    """

    def __init__(
        self,
        app: object,
        header_name: str = "X-Request-ID",
        generate: bool = True,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._header_name = header_name
        self._generate = generate

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Look up the client-provided ID using the configured header name.
        # Header lookup in Starlette is case-insensitive.
        client_id = request.headers.get(self._header_name.lower(), "")

        if self._generate and client_id and REQUEST_ID_PATTERN.match(client_id):
            request_id = client_id
        else:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers[self._header_name] = request_id
        return response
