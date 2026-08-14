"""GRPCDetector — gRPC sidecar detector client (v0.5.0).

Wraps the DESIGN.md Section 7.3 ``DetectorService`` contract into a gateway
:class:`Detector` so sidecar detectors participate in the pipeline like any
other detector:

- ``initialize()``: HealthCheck -> Initialize, applies ``DetectorInfo``.
- ``detect()``: maps ``DetectionContext`` -> ``DetectRequest`` and
  ``DetectResponse`` -> ``DetectionResult``.
- ``health_check()``: periodic HealthCheck (serving?).
- ``shutdown()``: remote Shutdown + channel close.

Uses the synchronous gRPC stub; blocking calls are offloaded via
``asyncio.to_thread`` and wrapped with ``asyncio.wait_for`` for timeout
enforcement (DESIGN.md Section 7.3.4).

grpcio is an optional dependency (``pip install z-llm-safety-gateway[grpc]``);
importing/instantiating without it raises a clear, actionable error.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import structlog
from google.protobuf.json_format import MessageToDict

from z_llm_safety_gateway.config.models import passthrough_config
from z_llm_safety_gateway.models import DetectionContext, DetectionResult

logger = structlog.get_logger(__name__)

#: Default gRPC call timeout when no per-detector/global timeout is resolved.
_DEFAULT_TIMEOUT_SECONDS = 5.0

#: Error message shown when grpcio is not installed.
_GRPC_MISSING_MESSAGE = (
    "grpcio is required for gRPC sidecar detectors. "
    "Install it with: pip install z-llm-safety-gateway[grpc]"
)


def _require_grpc() -> Any:
    """Import and return the ``grpc`` module, raising a clear error if absent."""
    try:
        import grpc  # noqa: PLC0415

        return grpc
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(_GRPC_MISSING_MESSAGE) from exc


class GRPCDetector:
    """A gateway Detector backed by a gRPC sidecar (DetectorService v1).

    Implements the structural Detector interface (name/category/description/
    version class attrs + async initialize/detect/health_check/shutdown), so it
    can be registered in the :class:`DetectorRegistry` and run by the pipeline
    engine (DESIGN.md Section 7.1).
    """

    name: str = "grpc"
    category: str = "grpc"
    description: str = "gRPC sidecar detector"
    version: str = "0.0.0"

    def __init__(self) -> None:
        self._grpc: Any = None
        self._channel: Any = None
        self._stub: Any = None
        self._detector_pb2: Any = None
        self._detector_pb2_grpc: Any = None
        self._endpoint: str = ""
        self._timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def initialize(self, config: dict[str, Any]) -> None:
        """HealthCheck + Initialize the sidecar and apply DetectorInfo.

        Args:
            config: Detector config including gateway-internal fields
                (``endpoint``, ``tls_enabled``, ``tls_ca_file``) plus
                optional ``timeout_seconds`` (injected by the gateway's
                config resolution, DESIGN.md Section 7.3.4) and any
                vendor-facing passthrough fields.

        Raises:
            ImportError: If grpcio is not installed.
            RuntimeError: If HealthCheck is not serving or Initialize fails.
        """
        self._grpc = _require_grpc()
        from z_llm_safety_gateway.plugins.grpc.proto.detector.v1 import (  # noqa: PLC0415
            detector_pb2,
            detector_pb2_grpc,
        )

        self._detector_pb2 = detector_pb2
        self._detector_pb2_grpc = detector_pb2_grpc

        self._endpoint = str(config.get("endpoint", ""))
        if not self._endpoint:
            raise ValueError("gRPC detector is missing required config: endpoint")

        self._timeout_seconds = float(
            config.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)
        )

        tls_enabled = bool(config.get("tls_enabled", False))
        tls_ca_file = str(config.get("tls_ca_file", "") or "")
        self._channel = self._build_channel(
            self._endpoint, tls_enabled=tls_enabled, tls_ca_file=tls_ca_file
        )
        self._stub = self._detector_pb2_grpc.DetectorServiceStub(self._channel)

        # 1. HealthCheck (must be serving before Initialize).
        health = await self._call(
            lambda: self._stub.HealthCheck(
                self._detector_pb2.HealthCheckRequest()
            ),
            "health check",
        )
        if health.status != "serving":
            raise RuntimeError(
                f"gRPC detector '{self._endpoint}' is not serving: {health.status}"
            )

        # 2. Initialize with passthrough config (endpoint/tls fields excluded).
        init_req = self._detector_pb2.InitializeRequest(
            detector_name=self.name,
            config={
                str(k): str(v) for k, v in passthrough_config(config).items()
            },
        )
        init_resp = await self._call(
            lambda: self._stub.Initialize(init_req), "initialize"
        )
        if not init_resp.success:
            raise RuntimeError(
                f"gRPC detector initialize failed: {init_resp.error_message}"
            )

        # 3. Apply DetectorInfo.
        if init_resp.info and init_resp.info.name:
            self.name = init_resp.info.name
            self.category = init_resp.info.category or self.category
            self.description = init_resp.info.description or self.description
            self.version = init_resp.info.version or self.version
        logger.info(
            "gRPC detector initialized",
            endpoint=self._endpoint,
            name=self.name,
            version=self.version,
        )

    async def detect(
        self,
        content: str,
        context: DetectionContext,
        *,
        timeout_seconds: float | None = None,
    ) -> DetectionResult:
        """Run detection on *content* via the sidecar.

        Args:
            content: Text content to analyze.
            context: Detection context.
            timeout_seconds: Optional per-call timeout override; falls back to
                the timeout resolved at initialize time.

        Returns:
            A DetectionResult mapped from the DetectResponse.
        """
        if self._stub is None:
            raise RuntimeError("GRPCDetector.detect() called before initialize()")

        request = self._detector_pb2.DetectRequest(
            content=content,
            direction=str(context.direction),
            request_id=str(context.request_id),
            user_id=str(context.user_id or ""),
            language=str(context.language or ""),
            message_index=context.message_index if context.message_index is not None else -1,
            metadata={
                str(k): str(v) for k, v in context.metadata.items()
            },
        )
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        response = await self._call(
            lambda: self._stub.Detect(request), "detect", timeout_seconds=timeout
        )
        return self._map_response(response)

    async def health_check(self) -> bool:
        """Return True when the sidecar reports ``serving``."""
        if self._stub is None:
            return False
        try:
            resp = await self._call(
                lambda: self._stub.HealthCheck(
                    self._detector_pb2.HealthCheckRequest()
                ),
                "health check",
            )
            return bool(resp.status == "serving")
        except Exception:
            logger.warning("gRPC health check failed", endpoint=self._endpoint, exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Call remote Shutdown and close the channel (failure-tolerant)."""
        if self._stub is not None:
            try:
                await self._call(
                    lambda: self._stub.Shutdown(
                        self._detector_pb2.ShutdownRequest()
                    ),
                    "shutdown",
                )
            except Exception:
                logger.warning("gRPC shutdown call failed", endpoint=self._endpoint, exc_info=True)
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:  # pragma: no cover - defensive
                logger.warning("gRPC channel close failed", exc_info=True)
        self._stub = None
        self._channel = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _build_channel(
        self, endpoint: str, *, tls_enabled: bool, tls_ca_file: str
    ) -> Any:
        """Build an insecure or TLS-secured gRPC channel (TC-GRPC-007)."""
        grpc = self._grpc
        if tls_enabled:
            if tls_ca_file:
                with open(tls_ca_file, "rb") as fh:
                    root_certs = fh.read()
                credentials = grpc.ssl_channel_credentials(
                    root_certificates=root_certs
                )
            else:
                credentials = grpc.ssl_channel_credentials()
            return grpc.secure_channel(endpoint, credentials)
        return grpc.insecure_channel(endpoint)

    async def _call(
        self,
        call: Callable[[], Any],
        operation: str,
        *,
        timeout_seconds: float | None = None,
    ) -> Any:
        """Run a blocking gRPC call off-thread with timeout (TC-GRPC-006)."""
        timeout = timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(call), timeout=timeout
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"gRPC {operation} timed out after {timeout}s "
                f"(endpoint={self._endpoint})"
            ) from exc

    def _map_response(self, response: Any) -> DetectionResult:
        """Map a DetectResponse to a DetectionResult (TC-GRPC-003/004)."""
        details: dict[str, Any] = {}
        if response.HasField("details"):
            details = MessageToDict(response.details)

        return DetectionResult(
            detector_name=response.detector_name or self.name,
            category=response.category or self.category,
            action=response.action,
            confidence=float(response.confidence),
            risk_level=response.risk_level,
            message=response.message,
            details=details,
            modified_content=response.modified_content or None,
        )
