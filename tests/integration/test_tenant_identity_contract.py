"""Production configuration and HTTP tenant identity contract tests."""

from __future__ import annotations

import warnings
from pathlib import Path

import httpx
from fastapi import Request
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app
from z_llm_safety_gateway.config.loader import load_config

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


def test_create_app_resolves_distinct_tenants_over_http(monkeypatch) -> None:
    """TC-CFG-703: create_app exposes distinct trusted Contexts over HTTP."""
    monkeypatch.setenv("ZLG_ACME_API_KEY", "http-acme-secret")
    monkeypatch.setenv("ZLG_GLOBEX_API_KEY", "http-globex-secret")
    app = create_app(str(MULTI_TENANT_EXAMPLE))

    @app.get("/tenant-contract")
    async def tenant_contract(request: Request) -> dict[str, object]:
        context = request.state.tenant_context
        return {
            "tenant_id": context.tenant_id,
            "identity_source": context.identity_source,
            "providers": [
                provider.name for provider in request.app.state.config.providers
            ],
            "input_flow": request.app.state.config.pipeline.input_flow,
            "output_flow": request.app.state.config.pipeline.output_flow,
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
    assert acme.json()["providers"] == globex.json()["providers"] == ["local"]
    assert acme.json()["input_flow"] == globex.json()["input_flow"]
    assert acme.json()["output_flow"] == globex.json()["output_flow"]
    assert "http-acme-secret" not in acme.text
    assert "http-globex-secret" not in globex.text
