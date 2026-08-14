"""End-to-end test for the example Python gRPC sidecar detector.

Boots the AcmeGuardService in-process, connects a gateway GRPCDetector
client, and verifies the full lifecycle: initialize -> detect (allow/block/
modify) -> health_check -> shutdown.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import grpc
import pytest

from acme_grpc_detector.detector.v1 import (
    detector_pb2,
    detector_pb2_grpc,
)
from acme_grpc_detector.server import AcmeGuardService
from z_llm_safety_gateway.models import DetectionContext
from z_llm_safety_gateway.plugins.grpc.client import GRPCDetector


@pytest.fixture
def sidecar_port() -> int:
    """Start AcmeGuardService on an in-process server; return its port."""
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    detector_pb2_grpc.add_DetectorServiceServicer_to_server(AcmeGuardService(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield port
    server.stop(0)


async def _connect(port: int) -> GRPCDetector:
    det = GRPCDetector()
    await det.initialize(
        {"endpoint": f"127.0.0.1:{port}", "sensitivity": "high", "api_key": "sk"}
    )
    return det


def test_grpc_sidecar_full_lifecycle(sidecar_port: int) -> None:
    """Initialize -> detect (allow/block/modify) -> health -> shutdown."""

    async def _run() -> None:
        det = await _connect(sidecar_port)
        # DetectorInfo applied.
        assert det.name == "acme_guard"
        assert det.version == "1.0.0"
        assert det.category == "custom"

        ctx = DetectionContext(direction="input", request_id="e2e-1")
        # allow
        allow = await det.detect("Hello from our happy customer!", ctx)
        assert allow.action == "allow"

        # block
        blocked = await det.detect("The secret-project launch is in Q3", ctx)
        assert blocked.action == "block"
        assert blocked.risk_level == "high"
        assert blocked.details["sensitivity"] == "high"  # passthrough config applied

        # modify
        modified = await det.detect("Update internal-ref doc before Friday", ctx)
        assert modified.action == "modify"
        assert modified.modified_content == "Update ************ doc before Friday"

        # health
        assert await det.health_check() is True

        # shutdown
        await det.shutdown()

    asyncio.run(_run())


def test_grpc_sidecar_health_serving(sidecar_port: int) -> None:
    """HealthCheck reports serving while the process is alive (before/after Initialize)."""

    async def _run() -> None:
        channel = grpc.insecure_channel(f"127.0.0.1:{sidecar_port}")
        stub = detector_pb2_grpc.DetectorServiceStub(channel)
        resp = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: stub.HealthCheck(detector_pb2.HealthCheckRequest())
            ),
            timeout=5,
        )
        assert resp.status == "serving"
        channel.close()

    asyncio.run(_run())
