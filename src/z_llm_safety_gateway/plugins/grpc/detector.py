"""gRPC sidecar detector support (v0.5.0).

Exposes :class:`GRPCDetector` and the optional grpcio guard used by tests.
"""

from z_llm_safety_gateway.plugins.grpc.client import GRPCDetector, _require_grpc

__all__ = ["GRPCDetector", "_require_grpc"]
