"""AcmeGuardServer — example Python gRPC sidecar detector.

A minimal but complete implementation of the gateway's ``DetectorService``
(proto/detector/v1/detector.proto).  Run it with:

    python -m acme_grpc_detector.server --port 50051

Then configure the gateway with:

    pipeline:
      detectors:
        input:
          - name: acme_guard
            type: grpc
            enabled: true
            config:
              endpoint: "localhost:50051"
              api_key: "sk-acme"      # passed through to InitializeRequest.config
              sensitivity: "high"     # passed through to InitializeRequest.config

The server applies a simple keyword policy: block messages containing
"secret-project", modify messages containing "internal-ref".
"""

from __future__ import annotations

import argparse
import hmac
import logging
import os
from concurrent import futures
from typing import Any

import grpc

from acme_grpc_detector.detector.v1 import (
    detector_pb2,
    detector_pb2_grpc,
)

logger = logging.getLogger(__name__)

BLOCK_KEYWORD = "secret-project"
REDACT_KEYWORD = "internal-ref"


class AcmeGuardService(detector_pb2_grpc.DetectorServiceServicer):
    """DetectorService v1 implementation with a keyword policy."""

    def __init__(self, expected_api_key: str | None = None) -> None:
        self._sensitivity: str = "medium"
        self._ready = True  # serving = process alive, before Initialize
        self._expected_api_key = (
            expected_api_key
            if expected_api_key is not None
            else os.getenv("DETECTOR_API_KEY")
        )

    # -- lifecycle ------------------------------------------------------ #
    def Initialize(self, request: detector_pb2.InitializeRequest, context: Any) -> detector_pb2.InitializeResponse:
        """Load passthrough config from the gateway."""
        supplied_api_key = request.config.get("api_key", "")
        if self._expected_api_key is not None and not hmac.compare_digest(
            supplied_api_key, self._expected_api_key
        ):
            return detector_pb2.InitializeResponse(
                success=False,
                error_message="invalid api_key",
            )
        self._sensitivity = request.config.get("sensitivity", "medium")
        logger.info("initialized with sensitivity=%s", self._sensitivity)
        return detector_pb2.InitializeResponse(
            success=True,
            info=detector_pb2.DetectorInfo(
                name="acme_guard",
                category="custom",
                description="Acme gRPC sidecar guard (example)",
                version="1.0.0",
                supported_languages=["en", "zh"],
            ),
        )

    def Shutdown(self, request: detector_pb2.ShutdownRequest, context: Any) -> detector_pb2.ShutdownResponse:
        self._ready = False
        logger.info("shutting down")
        return detector_pb2.ShutdownResponse(success=True)

    def HealthCheck(self, request: detector_pb2.HealthCheckRequest, context: Any) -> detector_pb2.HealthCheckResponse:
        # "serving" means the process is alive and can accept RPCs; the gateway
        # HealthChecks BEFORE Initialize (DESIGN.md Section 7.3.3), so the
        # initial state must be serving.
        return detector_pb2.HealthCheckResponse(
            status="serving" if self._ready else "not_serving"
        )

    # -- detection ------------------------------------------------------ #
    def Detect(self, request: detector_pb2.DetectRequest, context: Any) -> detector_pb2.DetectResponse:
        """Apply the keyword policy and return a DetectResponse."""
        content = request.content
        lowered = content.lower()

        if BLOCK_KEYWORD in lowered:
            return self._block(f"blocked keyword '{BLOCK_KEYWORD}'")
        if REDACT_KEYWORD in lowered:
            modified = content.replace(REDACT_KEYWORD, "*" * len(REDACT_KEYWORD))
            return detector_pb2.DetectResponse(
                detector_name="acme_guard",
                category="custom",
                action="modify",
                confidence=0.9,
                risk_level="medium",
                message="redacted keyword",
                modified_content=modified,
            )
        return detector_pb2.DetectResponse(
            detector_name="acme_guard",
            category="custom",
            action="allow",
            confidence=0.0,
            risk_level="low",
            message="ok",
        )

    def _block(self, message: str) -> detector_pb2.DetectResponse:
        return detector_pb2.DetectResponse(
            detector_name="acme_guard",
            category="custom",
            action="block",
            confidence=0.95,
            risk_level="high",
            message=message,
            details={"sensitivity": self._sensitivity},
        )


def serve(port: int) -> None:
    """Start the gRPC sidecar server (blocking)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    detector_pb2_grpc.add_DetectorServiceServicer_to_server(AcmeGuardService(), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    logger.info("acme_guard gRPC sidecar listening on :%d", port)
    server.wait_for_termination()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Acme gRPC sidecar detector (example)")
    parser.add_argument("--port", type=int, default=50051)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
