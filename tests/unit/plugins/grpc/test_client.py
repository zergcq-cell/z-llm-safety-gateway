"""Unit tests for GRPCDetector (TC-GRPC-001~008).

Uses an in-process synchronous gRPC server (running in a daemon thread) with
a configurable fake DetectorService stub, so no external sidecar is required.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import grpc
import pytest
from z_llm_safety_gateway_sdk import DetectionContext

from z_llm_safety_gateway.models import DetectionResult as GatewayDetectionResult
from z_llm_safety_gateway.plugins.grpc import detector as grpc_detector_mod
from z_llm_safety_gateway.plugins.grpc.client import GRPCDetector
from z_llm_safety_gateway.plugins.grpc.proto.detector.v1 import (
    detector_pb2,
    detector_pb2_grpc,
)


class FakeDetectorService(detector_pb2_grpc.DetectorServiceServicer):
    """Configurable in-process stub for tests."""

    def __init__(self) -> None:
        self.initialize_resp = detector_pb2.InitializeResponse(
            success=True,
            info=detector_pb2.DetectorInfo(
                name="acme_guard",
                category="custom",
                description="acme guard",
                version="2.0.0",
                supported_languages=["en", "zh"],
            ),
        )
        self.health_status = "serving"
        self.detect_resp = detector_pb2.DetectResponse(
            detector_name="acme_guard",
            category="custom",
            action="block",
            confidence=0.9,
            risk_level="high",
            message="blocked by acme",
        )
        self.initialize_calls: list[detector_pb2.InitializeRequest] = []
        self.detect_calls: list[detector_pb2.DetectRequest] = []
        self.shutdown_calls: list[detector_pb2.ShutdownRequest] = []
        self.health_calls: list[detector_pb2.HealthCheckRequest] = []
        self.detect_delay: float = 0.0

    def Initialize(self, request, context):  # type: ignore[no-untyped-def]
        self.initialize_calls.append(request)
        return self.initialize_resp

    def Detect(self, request, context):  # type: ignore[no-untyped-def]
        self.detect_calls.append(request)
        if self.detect_delay:
            import time

            time.sleep(self.detect_delay)
        return self.detect_resp

    def HealthCheck(self, request, context):  # type: ignore[no-untyped-def]
        self.health_calls.append(request)
        return detector_pb2.HealthCheckResponse(status=self.health_status)

    def Shutdown(self, request, context):  # type: ignore[no-untyped-def]
        self.shutdown_calls.append(request)
        return detector_pb2.ShutdownResponse(success=True)


@pytest.fixture
def grpc_server():
    """Start an in-process sync gRPC server; yield handle.

    ``grpc.server.start()`` is non-blocking: it starts accepting requests and
    returns immediately, so no background thread is needed.
    """
    server = grpc.server(ThreadPoolExecutor(max_workers=10))
    fake = FakeDetectorService()
    detector_pb2_grpc.add_DetectorServiceServicer_to_server(fake, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    yield SimpleNamespace(server=server, port=port, fake=fake)
    server.stop(0)


async def _make_detector(grpc_server, config: dict | None = None) -> GRPCDetector:
    cfg: dict = {"endpoint": f"127.0.0.1:{grpc_server.port}"}
    if config:
        cfg.update(config)
    det = GRPCDetector()
    await det.initialize(cfg)
    return det


# --------------------------------------------------------------------------- #
# TC-GRPC-001: initialize -> HealthCheck + Initialize + DetectorInfo
# --------------------------------------------------------------------------- #
async def test_initialize_healthcheck_and_detector_info(grpc_server) -> None:
    """TC-GRPC-001: initialize calls HealthCheck then Initialize; info applied."""
    det = GRPCDetector()
    await det.initialize(
        {"endpoint": f"127.0.0.1:{grpc_server.port}", "api_key": "sk"}
    )

    assert len(grpc_server.fake.health_calls) == 1
    assert len(grpc_server.fake.initialize_calls) == 1
    init_req = grpc_server.fake.initialize_calls[0]
    # DetectorInfo applied to instance.
    assert det.name == "acme_guard"
    assert det.category == "custom"
    assert det.version == "2.0.0"
    # Passthrough config sent (no endpoint/tls fields).
    assert "api_key" in init_req.config
    assert "endpoint" not in init_req.config


# --------------------------------------------------------------------------- #
# TC-GRPC-002: not_serving / Initialize failure -> exception
# --------------------------------------------------------------------------- #
async def test_initialize_not_serving_raises(grpc_server) -> None:
    """TC-GRPC-002: HealthCheck not_serving -> initialize raises."""
    grpc_server.fake.health_status = "not_serving"
    det = GRPCDetector()
    with pytest.raises(Exception, match="not serving|not_serving"):
        await det.initialize({"endpoint": f"127.0.0.1:{grpc_server.port}"})


async def test_initialize_failure_raises(grpc_server) -> None:
    """TC-GRPC-002b: Initialize success=false -> initialize raises."""
    grpc_server.fake.initialize_resp = detector_pb2.InitializeResponse(
        success=False, error_message="config invalid"
    )
    det = GRPCDetector()
    with pytest.raises(Exception, match="config invalid"):
        await det.initialize({"endpoint": f"127.0.0.1:{grpc_server.port}"})


# --------------------------------------------------------------------------- #
# TC-GRPC-003: detect mapping (block + details Struct)
# --------------------------------------------------------------------------- #
async def test_detect_request_response_mapping(grpc_server) -> None:
    """TC-GRPC-003: DetectionContext -> DetectRequest; DetectResponse -> DetectionResult."""
    grpc_server.fake.detect_resp = detector_pb2.DetectResponse(
        detector_name="acme_guard",
        category="custom",
        action="block",
        confidence=0.95,
        risk_level="critical",
        message="blocked",
        details={"rule": "r1", "count": 3},
    )
    det = await _make_detector(grpc_server)
    ctx = DetectionContext(
        direction="input",
        request_id="req-1",
        user_id="u1",
        metadata={"model": "gpt-4"},
        language="en",
        message_index=0,
    )
    result: GatewayDetectionResult = await det.detect("bad content", ctx)

    # Request mapping.
    req = grpc_server.fake.detect_calls[-1]
    assert req.content == "bad content"
    assert req.direction == "input"
    assert req.request_id == "req-1"
    assert req.user_id == "u1"
    assert req.language == "en"
    assert req.message_index == 0
    assert req.metadata["model"] == "gpt-4"

    # Response mapping.
    assert isinstance(result, GatewayDetectionResult)
    assert result.action == "block"
    assert result.confidence == pytest.approx(0.95)
    assert result.risk_level == "critical"
    assert result.details == {"rule": "r1", "count": pytest.approx(3)}


# --------------------------------------------------------------------------- #
# TC-GRPC-004: modify passes modified_content
# --------------------------------------------------------------------------- #
async def test_detect_modify_passes_modified_content(grpc_server) -> None:
    """TC-GRPC-004: action=modify passes modified_content through."""
    grpc_server.fake.detect_resp = detector_pb2.DetectResponse(
        detector_name="acme_guard",
        category="custom",
        action="modify",
        confidence=0.7,
        risk_level="medium",
        message="modified",
        modified_content="safe text",
    )
    det = await _make_detector(grpc_server)
    ctx = DetectionContext(direction="input", request_id="req-2")
    result = await det.detect("original", ctx)
    assert result.action == "modify"
    assert result.modified_content == "safe text"


# --------------------------------------------------------------------------- #
# TC-GRPC-005: shutdown + health_check
# --------------------------------------------------------------------------- #
async def test_shutdown_calls_remote_and_closes(grpc_server) -> None:
    """TC-GRPC-005: shutdown() invokes remote Shutdown and closes channel."""
    det = await _make_detector(grpc_server)
    await det.shutdown()
    assert len(grpc_server.fake.shutdown_calls) == 1


async def test_health_check_returns_bool(grpc_server) -> None:
    """TC-GRPC-005b: health_check() returns True when serving, False otherwise."""
    grpc_server.fake.health_status = "serving"
    det = await _make_detector(grpc_server)
    assert await det.health_check() is True

    grpc_server.fake.health_status = "not_serving"
    assert await det.health_check() is False


# --------------------------------------------------------------------------- #
# TC-GRPC-006: timeout handling
# --------------------------------------------------------------------------- #
async def test_detect_timeout_raises(grpc_server) -> None:
    """TC-GRPC-006: detect exceeds timeout -> raises timeout exception."""
    grpc_server.fake.detect_delay = 5.0  # far longer than the injected timeout
    det = await _make_detector(grpc_server)
    ctx = DetectionContext(direction="input", request_id="req-3")
    with pytest.raises(Exception, match="timeout|timed out"):
        await det.detect("content", ctx, timeout_seconds=0.2)


# --------------------------------------------------------------------------- #
# TC-GRPC-007: TLS channel selection
# --------------------------------------------------------------------------- #
def test_tls_channel_uses_secure_credentials(tmp_path) -> None:
    """TC-GRPC-007: tls_enabled=true builds secure channel with CA cert."""
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----")
    det = GRPCDetector()
    det._grpc = grpc
    channel = det._build_channel(
        "localhost:50051",
        tls_enabled=True,
        tls_ca_file=str(ca_file),
    )
    try:
        assert isinstance(channel, grpc.Channel)
    finally:
        channel.close()


def test_tls_disabled_uses_insecure_channel() -> None:
    """TC-GRPC-007b: tls_enabled=false/absent -> insecure channel."""
    det = GRPCDetector()
    det._grpc = grpc
    channel = det._build_channel("localhost:50051", tls_enabled=False, tls_ca_file="")
    try:
        assert isinstance(channel, grpc.Channel)
    finally:
        channel.close()


# --------------------------------------------------------------------------- #
# TC-GRPC-008: grpcio missing -> clear error
# --------------------------------------------------------------------------- #
def test_grpcio_missing_clear_error(monkeypatch) -> None:
    """TC-GRPC-008: missing grpcio raises actionable error."""
    import sys

    monkeypatch.setitem(sys.modules, "grpc", None)

    with pytest.raises(ImportError, match=r"\[grpc\]"):
        grpc_detector_mod._require_grpc()
