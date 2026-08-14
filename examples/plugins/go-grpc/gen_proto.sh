#!/usr/bin/env bash
# Generate Go gRPC stubs from the shared detector contract.
# Requires: protoc, protoc-gen-go, protoc-gen-go-grpc
#   go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
#   go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
set -euo pipefail
cd "$(dirname "$0")"
protoc \
  -I proto \
  --go_out=. --go_opt=module=github.com/acme/grpc-guard-example \
  --go-grpc_out=. --go-grpc_opt=module=github.com/acme/grpc-guard-example \
  proto/detector/v1/detector.proto
echo "Generated Go stubs in proto/detector/v1/"
