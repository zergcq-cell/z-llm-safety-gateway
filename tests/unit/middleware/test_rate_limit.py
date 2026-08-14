"""Unit tests for TokenBucket and RateLimitMiddleware.

Test cases: TC-RL-001~006
Covers: within-burst requests allowed (token consumed), bucket exhaustion
        rejected (429), config parsing of rate/burst/per/storage, 429 with
        Retry-After header and OpenAI-compatible body, concurrent token
        consumption safety, and per-IP limiting.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from z_llm_safety_gateway.config.models import ApiKeyConfig, AuthConfig, RateLimitConfig
from z_llm_safety_gateway.middleware.auth import AuthMiddleware
from z_llm_safety_gateway.middleware.rate_limit import RateLimitMiddleware
from z_llm_safety_gateway.ratelimit.token_bucket import TokenBucket

AUTH_HEADER = {"Authorization": "Bearer sk-a"}


def _create_app(
    rate_cfg: RateLimitConfig, *, with_auth: bool = False
) -> FastAPI:
    """Create a test app with RateLimitMiddleware (optionally behind auth).

    Ordering in Starlette: the last middleware added is outermost.  Adding
    RateLimit first (inner) then Auth (outer) yields the production order
    Auth -> RateLimit -> route, so request.state.api_key_name is set before
    the rate limiter runs when ``with_auth`` is True.
    """
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, config=rate_cfg)
    if with_auth:
        app.add_middleware(
            AuthMiddleware,
            config=AuthConfig(
                enabled=True, api_keys=[ApiKeyConfig(key="sk-a", name="app-a")]
            ),
        )

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, bool]:
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
# TC-RL-001: Requests within burst are allowed and consume a token.
# ---------------------------------------------------------------------------


def test_within_burst_allowed() -> None:
    """TC-RL-001: Requests within the bucket burst are allowed.

    GIVEN security.rate_limit with rate=10, burst=2, per=api_key and the
          api_key bucket still has tokens
    WHEN requests from that api_key arrive
    THEN they are allowed through (HTTP 200) and each consumes a token
    """
    cfg = RateLimitConfig(enabled=True, rate=10, burst=2, per="api_key")
    client = TestClient(_create_app(cfg, with_auth=True))

    for _ in range(2):
        response = client.get("/test", headers=AUTH_HEADER)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# TC-RL-002: A bucket that is exhausted rejects subsequent requests with 429.
# ---------------------------------------------------------------------------


def test_bucket_exhausted_rejected() -> None:
    """TC-RL-002: An exhausted bucket rejects the next request with HTTP 429.

    GIVEN an api_key's bucket has been exhausted (sustained over-speed)
    WHEN a subsequent request from that api_key arrives
    THEN it is rejected with HTTP 429
    """
    cfg = RateLimitConfig(enabled=True, rate=10, burst=1, per="api_key")
    client = TestClient(_create_app(cfg, with_auth=True))

    # Consume the single token.
    first = client.get("/test", headers=AUTH_HEADER)
    assert first.status_code == 200

    # Bucket is now empty -> rejected.
    response = client.get("/test", headers=AUTH_HEADER)
    assert response.status_code == 429


# ---------------------------------------------------------------------------
# TC-RL-003: rate/burst/per/storage parsed from security.rate_limit.
# ---------------------------------------------------------------------------


def test_config_parsing() -> None:
    """TC-RL-003: rate/burst/per/storage are read from security.rate_limit.

    GIVEN security.rate_limit={rate:10, burst:20, per:api_key, storage:memory}
    WHEN the rate limiter loads the configuration
    THEN it uses rate=10, burst=20, per=api_key, storage=memory
    AND per supports 'api_key' and 'ip'
    AND storage supports 'memory' (Redis deferred to v1.1+)
    """
    cfg = RateLimitConfig(rate=10, burst=20, per="api_key", storage="memory")
    assert cfg.rate == 10
    assert cfg.burst == 20
    assert cfg.per == "api_key"
    assert cfg.storage == "memory"

    # per supports the 'ip' dimension.
    assert RateLimitConfig(per="ip").per == "ip"

    # Invalid per / storage values are rejected by the model validators.
    with pytest.raises(ValidationError):
        RateLimitConfig(per="bogus")
    with pytest.raises(ValidationError):
        RateLimitConfig(storage="redis")


# ---------------------------------------------------------------------------
# TC-RL-004: 429 response carries Retry-After and an OpenAI-compatible body.
# ---------------------------------------------------------------------------


def test_429_retry_after() -> None:
    """TC-RL-004: A rate-limited response is 429 with Retry-After + OpenAI body.

    GIVEN a request is judged to be over the limit
    WHEN RateLimitMiddleware generates the rejection response
    THEN the response is HTTP 429
    AND it carries a Retry-After header (suggested retry seconds)
    AND the body is an OpenAI-compatible error format
    """
    cfg = RateLimitConfig(enabled=True, rate=10, burst=1, per="api_key")
    client = TestClient(_create_app(cfg, with_auth=True))

    client.get("/test", headers=AUTH_HEADER)  # consume the single token
    response = client.get("/test", headers=AUTH_HEADER)

    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert int(response.headers["Retry-After"]) >= 1

    body = response.json()
    assert "error" in body
    assert "type" in body["error"]
    assert "message" in body["error"]
    assert body["error"]["type"] == "rate_limit_error"


# ---------------------------------------------------------------------------
# TC-RL-005: Concurrent token consumption is atomic (no over-consumption).
# ---------------------------------------------------------------------------


async def test_concurrent_safety() -> None:
    """TC-RL-005: Concurrent token consumption is atomic and never negative.

    GIVEN multiple requests concurrently hit the same api_key bucket
    WHEN the limiter consumes tokens concurrently
    THEN consumption is atomic (asyncio.Lock) so no more than burst tokens
         are consumed and the token count never goes negative
    """
    burst = 5
    bucket = TokenBucket(rate=1000.0, burst=burst)

    results = await asyncio.gather(*[bucket.consume() for _ in range(50)])

    # Exactly `burst` requests succeed; the rest are rejected.
    assert sum(results) == burst
    # Tokens are not over-consumed: count is non-negative and below capacity.
    assert bucket.tokens >= 0.0
    assert bucket.tokens < 1.0


# ---------------------------------------------------------------------------
# TC-RL-006: per=ip limits by client IP.
# ---------------------------------------------------------------------------


def test_per_ip_limiting() -> None:
    """TC-RL-006: With per=ip, requests are limited per client IP.

    GIVEN security.rate_limit per=ip and a given IP is over the limit
    WHEN subsequent requests from that IP arrive
    THEN RateLimitMiddleware judges the IP over the limit and returns 429
    """
    cfg = RateLimitConfig(enabled=True, rate=10, burst=1, per="ip")
    client = TestClient(_create_app(cfg))

    first = client.get("/test")
    assert first.status_code == 200

    response = client.get("/test")
    assert response.status_code == 429
