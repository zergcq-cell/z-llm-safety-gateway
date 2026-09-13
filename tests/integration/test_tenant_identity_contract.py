"""Production configuration and HTTP tenant identity contract tests."""

from __future__ import annotations

import warnings
from pathlib import Path

import httpx
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.config.loader import load_config
from z_llm_safety_gateway.exceptions import ConfigValidationError
from z_llm_safety_gateway.middleware.auth import AuthMiddleware
from z_llm_safety_gateway.middleware.policy_resolution import (
    TenantPolicyResolutionMiddleware,
)
from z_llm_safety_gateway.middleware.rate_limit import RateLimitMiddleware
from z_llm_safety_gateway.tenancy import TenantContext

REPO_ROOT = Path(__file__).resolve().parents[2]
MULTI_TENANT_EXAMPLE = REPO_ROOT / "config/gateway.multi-tenant.example.yaml"


def test_legacy_config_files_and_protocol_remain_compatible(
    monkeypatch,
    respx_mock,
) -> None:
    """TC-CFG-701: Shipped legacy configs remain single-tenant compatible."""
    monkeypatch.setenv("OPENAI_API_KEY", "compat-openai-key")
    monkeypatch.setenv("ACME_API_KEY", "compat-grpc-key")

    with warnings.catch_warnings(record=True) as warning_list:
        for relative_path in ("config/gateway.yaml", "config/gateway.prod.yaml"):
            config = load_config(str(REPO_ROOT / relative_path))
            assert config.tenancy.enabled is False
            assert config.tenancy.tenants == ()
            assert all(key.tenant_id is None for key in config.security.auth.api_keys)
    assert not [warning for warning in warning_list if "tenant" in str(warning.message)]

    app = create_app(str(REPO_ROOT / "config/gateway.yaml"))

    @app.get("/legacy-tenant-contract")
    async def legacy_tenant_contract(request: Request) -> dict[str, str]:
        context = request.state.tenant_context
        return {
            "tenant_id": context.tenant_id,
            "identity_source": context.identity_source,
        }

    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "id": "legacy-sync",
                    "choices": [
                        {"message": {"role": "assistant", "content": "hello"}}
                    ],
                },
            ),
            httpx.Response(
                200,
                content=(
                    b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
                    b"data: [DONE]\n\n"
                ),
                headers={"content-type": "text/event-stream"},
            ),
        ]
    )
    client = TestClient(app)
    legacy_context = client.get("/legacy-tenant-contract")
    sync_response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    stream_response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hi"}],
            "stream": True,
        },
    )

    assert legacy_context.json() == {
        "tenant_id": "default",
        "identity_source": "legacy_single_tenant",
    }
    assert sync_response.status_code == 200
    assert sync_response.json()["id"] == "legacy-sync"
    assert stream_response.status_code == 200
    assert "data: [DONE]" in stream_response.text


def test_documented_multi_tenant_yaml_loads_with_environment_keys(
    monkeypatch,
    capsys,
) -> None:
    """TC-CFG-702: The documented env-based multi-tenant YAML is executable."""
    acme_secret = "example-acme-secret"
    globex_secret = "example-globex-secret"
    monkeypatch.setenv("ZLG_ACME_API_KEY", acme_secret)
    monkeypatch.setenv("ZLG_GLOBEX_API_KEY", globex_secret)
    acme_provider_secret = "example-acme-provider-secret"
    globex_provider_secret = "example-globex-provider-secret"
    monkeypatch.setenv("ZLG_ACME_PROVIDER_API_KEY", acme_provider_secret)
    monkeypatch.setenv("ZLG_GLOBEX_PROVIDER_API_KEY", globex_provider_secret)

    config = load_config(str(MULTI_TENANT_EXAMPLE))

    assert config.tenancy.enabled is True
    assert [tenant.id for tenant in config.tenancy.tenants] == ["acme", "globex"]
    assert [key.tenant_id for key in config.security.auth.api_keys] == [
        "acme",
        "globex",
    ]
    captured = capsys.readouterr()
    assert acme_secret not in captured.out
    assert acme_secret not in captured.err
    assert globex_secret not in captured.out
    assert globex_secret not in captured.err
    rendered = repr(config)
    assert acme_secret not in rendered
    assert globex_secret not in rendered
    assert acme_provider_secret not in rendered
    assert globex_provider_secret not in rendered


def test_create_app_resolves_distinct_tenants_over_http(monkeypatch, capsys) -> None:
    """TC-CFG-703/TEC-002: HTTP ignores client ownership claims."""
    monkeypatch.setenv("ZLG_ACME_API_KEY", "http-acme-secret")
    monkeypatch.setenv("ZLG_GLOBEX_API_KEY", "http-globex-secret")
    monkeypatch.setenv("ZLG_ACME_PROVIDER_API_KEY", "http-acme-provider-secret")
    monkeypatch.setenv("ZLG_GLOBEX_PROVIDER_API_KEY", "http-globex-provider-secret")
    app = create_app(str(MULTI_TENANT_EXAMPLE))

    middleware_classes = [registration.cls for registration in app.user_middleware]
    assert middleware_classes.index(AuthMiddleware) < middleware_classes.index(
        TenantPolicyResolutionMiddleware
    ) < middleware_classes.index(RateLimitMiddleware)

    @app.get("/tenant-contract")
    async def tenant_contract(request: Request) -> dict[str, object]:
        context = request.state.tenant_context
        observation = request.state.tenant_observation_context
        return {
            "tenant_id": context.tenant_id,
            "identity_source": context.identity_source,
            "policy_id": request.state.tenant_policy_context.policy_id,
            "routing_profile_id": (
                request.state.tenant_policy_context.routing_profile_id
            ),
            "providers": [
                provider.name for provider in request.app.state.config.providers
            ],
            "input_flow": request.app.state.config.pipeline.input_flow,
            "output_flow": request.app.state.config.pipeline.output_flow,
            "observation": {
                "scope": observation.scope.value,
                "tenant_id": observation.tenant_id,
                "policy_id": observation.policy_id,
            },
        }

    client = TestClient(app)
    acme = client.get(
        "/tenant-contract",
        headers={"Authorization": "Bearer http-acme-secret"},
    )
    globex = client.get(
        "/tenant-contract",
        headers={"Authorization": "Bearer http-globex-secret"},
    )

    assert acme.status_code == globex.status_code == 200
    assert acme.json()["tenant_id"] == "acme"
    assert globex.json()["tenant_id"] == "globex"
    assert acme.json()["identity_source"] == "api_key"
    assert globex.json()["identity_source"] == "api_key"
    assert acme.json()["policy_id"] == "acme-policy"
    assert globex.json()["policy_id"] == "globex-policy"
    assert acme.json()["routing_profile_id"] == "acme-policy"
    assert globex.json()["routing_profile_id"] == "globex-policy"
    assert acme.json()["observation"] == {
        "scope": "tenant",
        "tenant_id": "acme",
        "policy_id": "acme-policy",
    }
    assert globex.json()["observation"] == {
        "scope": "tenant",
        "tenant_id": "globex",
        "policy_id": "globex-policy",
    }
    rendered = repr(app.state.config)
    captured = capsys.readouterr()
    routine_output = captured.out + captured.err
    for secret in (
        "http-acme-secret",
        "http-globex-secret",
        "http-acme-provider-secret",
        "http-globex-provider-secret",
    ):
        assert secret not in rendered
        assert secret not in routine_output
    assert acme.json()["providers"] == globex.json()["providers"] == [
        "acme-local",
        "globex-local",
    ]
    assert acme.json()["input_flow"] == globex.json()["input_flow"]
    assert acme.json()["output_flow"] == globex.json()["output_flow"]
    assert "http-acme-secret" not in acme.text
    assert "http-globex-secret" not in globex.text


def test_documented_config_compiles_all_private_surfaces_without_secret_leak(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    """TC-CFG-705: example compiles models/factories/router with safe surfaces."""
    secrets = {
        "ZLG_ACME_API_KEY": "cfg705-acme-gateway-secret",
        "ZLG_GLOBEX_API_KEY": "cfg705-globex-gateway-secret",
        "ZLG_ACME_PROVIDER_API_KEY": "cfg705-acme-provider-secret",
        "ZLG_GLOBEX_PROVIDER_API_KEY": "cfg705-globex-provider-secret",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    config = load_config(str(MULTI_TENANT_EXAMPLE))
    app = create_app(str(MULTI_TENANT_EXAMPLE))
    acme_bundle = app.state.tenant_policy_resolver.resolve(
        TenantContext("acme", "api_key")
    ).bundle

    assert config.tenancy.policies[0].capabilities[0].detector_name == "sensitive_words"
    assert [detector.name for detector in acme_bundle.input_detectors] == [
        "sensitive_words"
    ]
    assert acme_bundle.router_view.models_provider.config.name == "acme-local"
    assert acme_bundle.router_view.route("any-model").config.name == "acme-local"

    invalid = tmp_path / "invalid-secret-example.yaml"
    invalid.write_text(
        MULTI_TENANT_EXAMPLE.read_text().replace(
            'models_provider: "acme-local"',
            'models_provider: "missing-provider"',
            1,
        )
    )
    with pytest.raises(ConfigValidationError) as exc_info:
        load_config(str(invalid))

    documentation = "\n".join(
        path.read_text()
        for root in (
            REPO_ROOT / "changes/2026-09-01-tenant-flow-policy-resolution/specs",
            REPO_ROOT
            / "changes/2026-09-01-tenant-flow-policy-resolution/canonical",
        )
        for path in root.rglob("*")
        if path.is_file()
    )
    captured = capsys.readouterr()
    safe_surfaces = (
        repr(config),
        repr(app.state.tenant_policy_resolver.resolve(TenantContext("acme", "api_key")).context),
        str(exc_info.value),
        captured.out,
        captured.err,
        documentation,
    )
    for secret in secrets.values():
        assert all(secret not in surface for surface in safe_surfaces)
