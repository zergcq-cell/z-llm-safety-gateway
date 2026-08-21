# Python gRPC Sidecar Detector Example

A complete example of a **gRPC sidecar** plugin: a standalone server process
that implements `DetectorService` v1 (`proto/detector/v1/detector.proto`).
The gateway talks to it over gRPC; the detector can be written in any
language.

## What it does

`AcmeGuardService` enforces a keyword policy over gRPC:
- blocks content containing `secret-project`
- redacts content containing `internal-ref`
- reads `sensitivity` from the gateway's passthrough config
- validates the passthrough `api_key` against the sidecar's `DETECTOR_API_KEY`

## Files

| File | Purpose |
|------|---------|
| `src/acme_grpc_detector/server.py` | DetectorService v1 implementation + `serve()` entry point |
| `src/acme_grpc_detector/detector/v1/` | Generated protobuf/gRPC stubs (committed) |
| `proto/detector/v1/detector.proto` | Contract source (same as gateway `proto/`) |
| `gen_proto.sh` | Regenerate stubs after contract changes |
| `tests/test_server.py` | End-to-end test: boots the service, drives it with the gateway `GRPCDetector` client |

## Run the sidecar

```bash
# 1. install deps
pip install grpcio protobuf
pip install -e ../../../sdk

# 2. run the server
python -m acme_grpc_detector.server --port 50051
```

## Configure the gateway

```yaml
pipeline:
  detectors:
    input:
      - name: acme_guard
        type: grpc
        enabled: true
        config:
          endpoint: "localhost:50051"
          api_key: "sk-acme"       # passthrough -> InitializeRequest.config
          sensitivity: "high"      # passthrough -> InitializeRequest.config
```

## Run the tests

```bash
PYTHONPATH=../../../sdk/src:src python3 -m pytest tests -q
```

The test boots the service in-process and drives the complete lifecycle
(HealthCheck → Initialize → Detect allow/block/modify → HealthCheck →
Shutdown) through the gateway's own `GRPCDetector` client.

## Lifecycle contract (important)

- `HealthCheck` reports `serving` while the process is alive — the gateway
  calls it **before** `Initialize` (DESIGN.md §7.3.3).
- `Initialize` receives the passthrough config (gateway-internal fields like
  `endpoint`/`tls_*` are stripped).
- `DetectResponse.details` is a `google.protobuf.Struct` (arbitrary JSON).
