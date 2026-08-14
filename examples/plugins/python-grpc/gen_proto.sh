#!/usr/bin/env bash
# Regenerate gRPC stubs for this example from the shared contract.
# Requires: pip install grpcio-tools
set -euo pipefail
cd "$(dirname "$0")"
python3 -m grpc_tools.protoc \
  -I proto \
  --python_out=src/acme_grpc_detector \
  --grpc_python_out=src/acme_grpc_detector \
  proto/detector/v1/detector.proto
echo "Generated stubs in src/acme_grpc_detector/detector/v1/"
