"""Safety headers middleware — injects safety-related response headers.

Reads the pipeline result from ``request.state`` (set by the route handler)
and injects the appropriate safety headers into the response:

- ``X-Safety-Action``: the final action (allow, block, flag, modify).
- ``X-Safety-Risk-Level``: the overall risk level (only when action != allow).

When no pipeline runs (e.g., no detectors configured), the action defaults
to ``"allow"`` and no risk-level header is injected.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SafetyHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that injects safety-related headers into responses.

    - Reads ``request.state.safety_action`` (default: ``"allow"``).
    - Reads ``request.state.safety_risk_level`` (default: ``None``).
    - Injects ``X-Safety-Action`` with the pipeline's final action.
    - Injects ``X-Safety-Risk-Level`` when action is not ``"allow"``
      and a risk level is available.

    Registration order: SafetyHeaders should be added BEFORE RequestID
    so that RequestID is outermost (processes request first, response last).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response = await call_next(request)

        # Read pipeline result from request.state, defaulting to "allow".
        safety_action = getattr(request.state, "safety_action", "allow")
        safety_risk_level = getattr(request.state, "safety_risk_level", None)

        response.headers["X-Safety-Action"] = safety_action
        if safety_action != "allow" and safety_risk_level:
            response.headers["X-Safety-Risk-Level"] = safety_risk_level

        return response
