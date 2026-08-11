"""Request ID middleware — propagates or generates a UUID v4 request ID.

Checks the X-Request-ID header from the client:
- If present and valid (matches ^[a-zA-Z0-9_-]{1,128}$), uses the client value.
- If absent, empty, or invalid, generates a UUID v4.

Stores the request ID in request.state.request_id for downstream use and
injects X-Request-ID header into the response.
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

    - Checks the X-Request-ID header from the client.
    - If valid (matches ^[a-zA-Z0-9_-]{1,128}$), uses the client-provided value.
    - If absent, empty, or invalid, generates a UUID v4.
    - Stores the request ID in request.state.request_id.
    - Injects X-Request-ID header into the response.

    This sanitization prevents log injection (newline/control characters
    breaking JSONL) and header injection (CRLF characters in headers).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        client_id = request.headers.get("x-request-id", "")

        if client_id and REQUEST_ID_PATTERN.match(client_id):
            request_id = client_id
        else:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
