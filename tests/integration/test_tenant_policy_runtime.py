"""Production wiring for tenant policy Flow and Provider runtime bundles."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from z_llm_safety_gateway.app import create_app


def _config(path: Path, *, streaming_mode: str = "sliding_window") -> Path:
    path.write_text(
        """
server: {host: 127.0.0.1, port: 8080}
providers:
  - name: global-first
    type: openai_compatible
    base_url: https://global.invalid/v1
  - name: acme-provider
    type: openai_compatible
    base_url: https://acme.invalid/v1
  - name: globex-provider
    type: openai_compatible
    base_url: https://globex.invalid/v1
routing: {}
pipeline:
  streaming:
    mode: STREAMING_MODE
    window_size: 30
    overlap: 5
    post_audit: true
flows:
  - contract_version: "1.0"
    flow_id: tenant-input
    version: 1.0.0
    input_schema: safety.text.v1
    output_schema: safety.detector-result.v1
    reducer_capability_id: detector-result-reducer
    nodes:
      - kind: capability
        contract_version: "1.0"
        node_id: sensitive-check
        capability_id: detector.sensitive_words
        input_schema: safety.text.v1
        output_schema: safety.detector-result.v1
        policy:
          timeout: {seconds: 5, action: fail_closed}
          failure: {action: fail_closed}
          availability:
            required: true
            on_unavailable: fail_closed
            on_circuit_open: fail_closed
          degradation:
            allowed: false
            emit_evidence: true
            emit_metrics: true
          stop: {signals: [safety.block]}
tenancy:
  enabled: true
  tenants:
    - {id: acme, policy_id: acme-policy}
    - {id: globex, policy_id: globex-policy}
  policies:
    - id: acme-policy
      input_flow: {flow_id: tenant-input, version: 1.0.0}
      output_flow: {flow_id: tenant-input, version: 1.0.0}
      capabilities:
        - capability_id: detector.sensitive_words
          detector_name: sensitive_words
          config:
            words: [acme-private-block]
            block_threshold: 1
            flag_threshold: 0.5
      routing:
        models_provider: acme-provider
        rules: [{pattern: "shared-*", provider: acme-provider}]
    - id: globex-policy
      input_flow: {flow_id: tenant-input, version: 1.0.0}
      output_flow: {flow_id: tenant-input, version: 1.0.0}
      capabilities:
        - capability_id: detector.sensitive_words
          detector_name: sensitive_words
          config:
            words: [globex-private-block]
            block_threshold: 1
            flag_threshold: 0.5
      routing:
        models_provider: globex-provider
        rules: [{pattern: "shared-*", provider: globex-provider}]
security:
  auth:
    enabled: true
    api_keys:
      - {key: acme-key, name: acme-app, tenant_id: acme}
      - {key: globex-key, name: globex-app, tenant_id: globex}
audit:
  enabled: false
  stdout: false
  file: {enabled: false}
"""
    )
    path.write_text(path.read_text().replace("STREAMING_MODE", streaming_mode))
    return path


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _sse_response(text: str) -> httpx.Response:
    payload = json.dumps({"choices": [{"delta": {"content": text}}]})
    return httpx.Response(
        200,
        content=f"data: {payload}\n\ndata: [DONE]\n\n",
        headers={"content-type": "text/event-stream"},
    )


@respx.mock
def test_real_app_uses_tenant_flow_binding_and_router_bundle(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TC-DDF-008/009 + TC-PROXY-013/015: one captured bundle drives chat."""
    acme_upstream = respx.post(
        "https://acme.invalid/v1/chat/completions"
    ).respond(200, json={"id": "acme-response", "choices": []})
    globex_upstream = respx.post(
        "https://globex.invalid/v1/chat/completions"
    ).respond(200, json={"id": "globex-response", "choices": []})
    global_upstream = respx.post(
        "https://global.invalid/v1/chat/completions"
    ).respond(200, json={"id": "global-response", "choices": []})
    app = create_app(str(_config(tmp_path / "tenant-runtime.yaml")))
    client = TestClient(app)

    blocked = client.post(
        "/v1/chat/completions",
        headers={
            **_headers("acme-key"),
            "X-Tenant-ID": "globex",
            "X-Policy-ID": "globex-policy",
            "X-Provider": "globex-provider",
        },
        json={
            "model": "shared-model",
            "messages": [{"role": "user", "content": "acme-private-block"}],
            "tenant_id": "globex",
            "policy_id": "globex-policy",
            "provider": "globex-provider",
        },
    )
    globex = client.post(
        "/v1/chat/completions",
        headers=_headers("globex-key"),
        json={
            "model": "shared-model",
            "messages": [{"role": "user", "content": "acme-private-block"}],
        },
    )

    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "safety_input_blocked"
    assert globex.status_code == 200
    assert globex.json()["id"] == "globex-response"
    assert acme_upstream.call_count == 0
    assert globex_upstream.call_count == 1
    assert global_upstream.call_count == 0
    assert json.loads(globex_upstream.calls[0].request.content) == {
        "model": "shared-model",
        "messages": [{"role": "user", "content": "acme-private-block"}],
    }

    bundles = app.state.tenant_policy_resolver._bundles
    assert bundles["acme-policy"].engine is not bundles["globex-policy"].engine
    assert bundles["acme-policy"].status_registry is not bundles["globex-policy"].status_registry
    routine_output = capsys.readouterr()
    assert "acme-private-block" not in routine_output.out + routine_output.err
    assert "globex-private-block" not in routine_output.out + routine_output.err


@respx.mock
def test_concurrent_requests_keep_sync_output_policy_snapshots_isolated(
    tmp_path: Path,
) -> None:
    """TC-TPR-005: a real concurrency barrier cannot cross sync snapshots."""
    arrived = 0
    both_arrived = asyncio.Event()

    async def wait_for_peer() -> None:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_arrived.set()
        await asyncio.wait_for(both_arrived.wait(), timeout=5)

    async def acme_response(_request: httpx.Request) -> httpx.Response:
        await wait_for_peer()
        return httpx.Response(
            200,
            json={
                "id": "acme-sync-output",
                "choices": [
                    {"message": {"content": "globex-private-block"}}
                ],
            },
        )

    async def globex_response(_request: httpx.Request) -> httpx.Response:
        await wait_for_peer()
        return httpx.Response(
            200,
            json={
                "id": "globex-sync-output",
                "choices": [
                    {"message": {"content": "globex-private-block"}}
                ],
            },
        )

    acme_upstream = respx.post(
        "https://acme.invalid/v1/chat/completions"
    ).mock(side_effect=acme_response)
    globex_upstream = respx.post(
        "https://globex.invalid/v1/chat/completions"
    ).mock(side_effect=globex_response)
    app = create_app(str(_config(tmp_path / "tenant-concurrent-sync.yaml")))

    async def request(client: httpx.AsyncClient, key: str) -> httpx.Response:
        return await client.post(
            "/v1/chat/completions",
            headers=_headers(key),
            json={"model": "shared-model", "messages": []},
        )

    async def exercise() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await asyncio.gather(
                request(client, "acme-key"),
                request(client, "globex-key"),
            )

    acme, globex = asyncio.run(exercise())

    assert acme.status_code == 200
    assert acme.json()["id"] == "acme-sync-output"
    assert globex.status_code == 422
    assert globex.json()["error"]["code"] == "safety_output_blocked"
    assert acme_upstream.call_count == globex_upstream.call_count == 1


@respx.mock
def test_models_endpoint_uses_explicit_tenant_models_provider(tmp_path: Path) -> None:
    """TC-PROXY-016: tenant models use explicit Provider, never global first."""
    acme_body = b'{"object":"list","data":[{"id":"acme-model"}]}'
    globex_body = b'{"object":"list","data":[{"id":"globex-model"}]}'
    acme_models = respx.get("https://acme.invalid/v1/models").respond(
        200, content=acme_body, headers={"content-type": "application/vnd.openai+json"}
    )
    globex_models = respx.get("https://globex.invalid/v1/models").respond(
        200, content=globex_body, headers={"content-type": "application/vnd.openai+json"}
    )
    global_models = respx.get("https://global.invalid/v1/models").respond(
        200, json={"object": "list", "data": [{"id": "global-model"}]}
    )
    client = TestClient(create_app(str(_config(tmp_path / "tenant-models.yaml"))))

    acme = client.get("/v1/models", headers=_headers("acme-key"))
    globex = client.get("/v1/models", headers=_headers("globex-key"))

    assert acme.status_code == globex.status_code == 200
    assert acme.json()["data"] == [{"id": "acme-model"}]
    assert globex.json()["data"] == [{"id": "globex-model"}]
    assert acme.content == acme_body
    assert globex.content == globex_body
    assert acme.headers["content-type"] == "application/vnd.openai+json"
    assert acme_models.call_count == globex_models.call_count == 1
    assert global_models.call_count == 0


def test_ready_refreshes_every_tenant_registry(tmp_path: Path) -> None:
    """TC-DDF-011: production readiness fails if one required tenant guard fails."""
    app = create_app(str(_config(tmp_path / "tenant-ready.yaml")))
    bundle = app.state.tenant_runtime_bundles[0]

    async def unhealthy() -> bool:
        return False

    bundle.input_detectors[0].health_check = unhealthy
    with TestClient(app) as client:
        response = client.get("/ready", headers=_headers("acme-key"))

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["detectors"]["configured"] == 2


@pytest.mark.parametrize("streaming_mode", ("sliding_window", "buffer"))
@respx.mock
def test_tenant_bundle_drives_streaming_output_paths(
    tmp_path: Path,
    streaming_mode: str,
) -> None:
    """TC-TPR-005/CFG-704: SSE stages retain tenant Flow and Provider state."""
    acme_upstream = respx.post(
        "https://acme.invalid/v1/chat/completions"
    ).mock(return_value=_sse_response("globex-private-block"))
    globex_upstream = respx.post(
        "https://globex.invalid/v1/chat/completions"
    ).mock(return_value=_sse_response("globex-private-block"))
    global_upstream = respx.post(
        "https://global.invalid/v1/chat/completions"
    ).mock(return_value=_sse_response("global"))
    app = create_app(
        str(_config(tmp_path / f"tenant-{streaming_mode}.yaml", streaming_mode=streaming_mode))
    )

    with TestClient(app) as client:
        acme = client.post(
            "/v1/chat/completions",
            headers=_headers("acme-key"),
            json={
                "model": "shared-model",
                "messages": [{"role": "user", "content": "safe"}],
                "stream": True,
            },
        )
        globex = client.post(
            "/v1/chat/completions",
            headers=_headers("globex-key"),
            json={
                "model": "shared-model",
                "messages": [{"role": "user", "content": "safe"}],
                "stream": True,
            },
        )

    assert acme.status_code == globex.status_code == 200
    assert "globex-private-block" in acme.text
    expected_event = "safety_block" if streaming_mode == "buffer" else "safety_recall"
    assert expected_event in globex.text
    assert acme_upstream.call_count == globex_upstream.call_count == 1
    assert global_upstream.call_count == 0


@respx.mock
def test_tenant_bundle_drives_async_output_and_recall(tmp_path: Path) -> None:
    """TC-TPR-005: async output detection retains policy-local Detector state."""
    config_path = _config(tmp_path / "tenant-async.yaml")
    config_path.write_text(
        config_path.read_text().replace(
            "pipeline:\n",
            "pipeline:\n"
            "  output_detection:\n"
            "    mode: async\n"
            "    recall:\n"
            "      webhook_url: https://recall.invalid/hook\n",
            1,
        )
    )
    acme_upstream = respx.post(
        "https://acme.invalid/v1/chat/completions"
    ).respond(
        200,
        json={
            "id": "acme-async",
            "choices": [{"message": {"content": "globex-private-block"}}],
        },
    )
    globex_upstream = respx.post(
        "https://globex.invalid/v1/chat/completions"
    ).respond(
        200,
        json={
            "id": "globex-async",
            "choices": [{"message": {"content": "globex-private-block"}}],
        },
    )
    recall = respx.post("https://recall.invalid/hook").respond(204)
    app = create_app(str(config_path))

    with TestClient(app) as client:
        acme = client.post(
            "/v1/chat/completions",
            headers=_headers("acme-key"),
            json={"model": "shared-model", "messages": []},
        )
        globex = client.post(
            "/v1/chat/completions",
            headers=_headers("globex-key"),
            json={"model": "shared-model", "messages": []},
        )

    assert acme.json()["id"] == "acme-async"
    assert globex.json()["id"] == "globex-async"
    assert acme_upstream.call_count == globex_upstream.call_count == 1
    assert recall.call_count == 1
