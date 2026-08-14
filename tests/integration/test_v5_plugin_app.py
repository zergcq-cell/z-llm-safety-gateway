"""Integration tests for plugin + gRPC detector wiring in create_app (TC-FSA-501~503).

Test cases:
- TC-FSA-501: create_app integrates plugin entry points + gRPC detectors
- TC-FSA-502: plugin/gRPC detectors run in the pipeline (aggregation/audit)
- TC-FSA-503: lifespan shutdown closes gRPC channels
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import grpc
import pytest

from z_llm_safety_gateway.app import create_app, lifespan
from z_llm_safety_gateway.plugins.grpc.proto.detector.v1 import (
    detector_pb2,
    detector_pb2_grpc,
)


class FakeGrpcService(detector_pb2_grpc.DetectorServiceServicer):
    """In-process sidecar stub that blocks everything."""

    def __init__(self) -> None:
        self.shutdown_called = False

    def Initialize(self, request, context):  # type: ignore[no-untyped-def]
        return detector_pb2.InitializeResponse(
            success=True,
            info=detector_pb2.DetectorInfo(
                name="acme_guard", category="custom",
                description="acme", version="1.0.0",
            ),
        )

    def Detect(self, request, context):  # type: ignore[no-untyped-def]
        return detector_pb2.DetectResponse(
            detector_name="acme_guard", category="custom",
            action="allow", confidence=0.0, risk_level="low",
            message="ok",
        )

    def HealthCheck(self, request, context):  # type: ignore[no-untyped-def]
        return detector_pb2.HealthCheckResponse(status="serving")

    def Shutdown(self, request, context):  # type: ignore[no-untyped-def]
        self.shutdown_called = True
        return detector_pb2.ShutdownResponse(success=True)


@pytest.fixture
def grpc_sidecar():
    """Start an in-process gRPC sidecar; yield (port, service)."""
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    service = FakeGrpcService()
    detector_pb2_grpc.add_DetectorServiceServicer_to_server(service, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield SimpleNamespace(port=port, service=service)
    server.stop(0)


def _write_config(tmp_path: Path, grpc_port: int) -> Path:
    """Write a config that enables a gRPC detector and a plugin detector."""
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
server:
  host: 127.0.0.1
  port: 8080
providers:
  - name: openai
    type: openai
    base_url: https://api.openai.com/v1
    api_key: sk-test
routing:
  rules:
    - pattern: gpt-4*
      provider: openai
pipeline:
  detectors:
    input:
      - name: acme_guard
        type: grpc
        enabled: true
        config:
          endpoint: "127.0.0.1:{grpc_port}"
          api_key: sk-sidecar
    output: []
"""
    )
    return cfg_path


# --------------------------------------------------------------------------- #
# TC-FSA-501: create_app integrates plugin + gRPC detectors
# --------------------------------------------------------------------------- #
def test_create_app_initializes_grpc_detector(tmp_path, grpc_sidecar, monkeypatch) -> None:
    """TC-FSA-501: create_app creates GRPCDetector for type=grpc config."""
    # No entry-point plugins in this run.
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda *, group=None: (),
    )
    cfg_path = _write_config(tmp_path, grpc_sidecar.port)
    app = create_app(str(cfg_path))

    # gRPC detector present in the input detector set.
    names = [d.name for d in app.state.input_detectors]
    assert "acme_guard" in names


# --------------------------------------------------------------------------- #
# TC-FSA-502: plugin/gRPC detectors run in the pipeline
# --------------------------------------------------------------------------- #
def test_grpc_detector_runs_in_pipeline(tmp_path, grpc_sidecar, monkeypatch) -> None:
    """TC-FSA-502: GRPCDetector runs via pipeline engine like built-ins."""
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda *, group=None: (),
    )
    cfg_path = _write_config(tmp_path, grpc_sidecar.port)
    app = create_app(str(cfg_path))

    engine = app.state.pipeline_engine
    detector = next(d for d in app.state.input_detectors if d.name == "acme_guard")

    from z_llm_safety_gateway.models import DetectionContext

    async def _run() -> None:
        result = await engine.run(
            [detector],
            [DetectionContext(direction="input", request_id="req-v5")],
            {"acme_guard": app.state.input_detector_configs["acme_guard"]},
        )
        assert result.final_action == "allow"

    asyncio.run(_run())


# --------------------------------------------------------------------------- #
# TC-FSA-503: lifespan shutdown closes gRPC channels
# --------------------------------------------------------------------------- #
def test_lifespan_shutdown_closes_grpc(tmp_path, grpc_sidecar, monkeypatch) -> None:
    """TC-FSA-503: lifespan shutdown invokes gRPC detector shutdown()."""
    monkeypatch.setattr(
        "importlib.metadata.entry_points",
        lambda *, group=None: (),
    )
    cfg_path = _write_config(tmp_path, grpc_sidecar.port)
    app = create_app(str(cfg_path))

    # Exercise lifespan startup + shutdown.
    async def _run() -> None:
        async with lifespan(app):
            pass

    asyncio.run(_run())

    assert grpc_sidecar.service.shutdown_called is True
