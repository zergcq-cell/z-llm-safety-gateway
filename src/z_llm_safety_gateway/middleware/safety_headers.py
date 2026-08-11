"""Safety headers middleware — injects safety-related response headers.

Phase 1 behavior (no safety detection):
- Injects X-Safety-Action: "allow" into all responses.
- Does NOT inject X-Safety-Risk-Level when action is "allow".
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SafetyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects safety-related headers into responses.

    - Injects X-Safety-Action: "allow" (Phase 1 has no safety detection).
    - Does NOT inject X-Safety-Risk-Level when action is "allow".

    Registration order: SafetyHeaders should be added BEFORE RequestID
    so that RequestID is outermost (processes request first, response last).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Safety-Action"] = "allow"
        return response
