"""Unit tests for SafetyHeadersMiddleware dynamic header injection — TC-FAST-007~008.

Covers: dynamic X-Safety-Action header reflecting pipeline result, and
X-Safety-Risk-Level header set when action != allow.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from z_llm_safety_gateway.middleware.request_id import RequestIDMiddleware
from z_llm_safety_gateway.middleware.safety_headers import SafetyHeadersMiddleware


def _create_test_app(
    safety_action: str | None = None,
    safety_risk_level: str | None = None,
) -> FastAPI:
    """Create a test app that sets request.state safety attributes.

    The /test endpoint sets request.state.safety_action and
    request.state.safety_risk_level to the provided values, simulating
    what the pipeline-aware route handler would do.
    """
    app = FastAPI()
    app.add_middleware(SafetyHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> JSONResponse:
        if safety_action is not None:
            request.state.safety_action = safety_action
        if safety_risk_level is not None:
            request.state.safety_risk_level = safety_risk_level
        return JSONResponse({"ok": True})

    return app


# ---------------------------------------------------------------------------
# TC-FAST-007: Dynamic X-Safety-Action header reflects pipeline result.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action,expected_header",
    [
        ("allow", "allow"),
        ("flag", "flag"),
        ("modify", "modify"),
        ("block", "block"),
    ],
)
def test_safety_action_header_reflects_pipeline_result(
    action: str, expected_header: str
) -> None:
    """TC-FAST-007: X-Safety-Action header reflects the pipeline's final action.

    GIVEN a gateway with SafetyHeadersMiddleware
    WHEN the route handler sets request.state.safety_action to various values
    THEN the X-Safety-Action response header matches the set value
    """
    app = _create_test_app(safety_action=action)
    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers["x-safety-action"] == expected_header


def test_safety_action_defaults_to_allow_when_not_set() -> None:
    """TC-FAST-007 (cont.): X-Safety-Action defaults to 'allow' when not set.

    GIVEN a gateway with SafetyHeadersMiddleware
    WHEN the route handler does NOT set request.state.safety_action
    THEN the X-Safety-Action response header is 'allow' (default)
    """
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers["x-safety-action"] == "allow"


# ---------------------------------------------------------------------------
# TC-FAST-008: X-Safety-Risk-Level header set when action != allow.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action,risk_level,expect_risk_header",
    [
        ("allow", None, False),
        ("allow", "low", False),
        ("flag", "medium", True),
        ("modify", "high", True),
        ("block", "critical", True),
    ],
)
def test_risk_level_header_set_when_action_not_allow(
    action: str, risk_level: str | None, expect_risk_header: bool
) -> None:
    """TC-FAST-008: X-Safety-Risk-Level header is set only when action != allow.

    GIVEN a gateway with SafetyHeadersMiddleware
    WHEN the route handler sets safety_action and safety_risk_level
    THEN the X-Safety-Risk-Level header is present when action != 'allow'
    AND the X-Safety-Risk-Level header is absent when action == 'allow'
    """
    app = _create_test_app(safety_action=action, safety_risk_level=risk_level)
    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers["x-safety-action"] == action

    if expect_risk_header:
        assert "x-safety-risk-level" in response.headers
        assert response.headers["x-safety-risk-level"] == risk_level
    else:
        assert "x-safety-risk-level" not in response.headers


def test_risk_level_not_set_when_action_allow_even_if_risk_provided() -> None:
    """TC-FAST-008 (cont.): Risk-level header suppressed when action is 'allow'.

    GIVEN a gateway with SafetyHeadersMiddleware
    WHEN safety_action is 'allow' but safety_risk_level is 'high'
    THEN the X-Safety-Risk-Level header is NOT set (action is allow)
    """
    app = _create_test_app(safety_action="allow", safety_risk_level="high")
    client = TestClient(app)

    response = client.get("/test")

    assert response.status_code == 200
    assert response.headers["x-safety-action"] == "allow"
    assert "x-safety-risk-level" not in response.headers
