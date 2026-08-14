# Go gRPC Sidecar Detector Example

Reference source for implementing `DetectorService` v1 in **Go**.

> **Validation status:** This example was authored without a Go toolchain in
> the development environment and has **not been compiled or executed** there.
> It follows the same lifecycle and contract semantics as the Python gRPC
> example and is intended as a starting point, not a verified binary.

## What it does

`acmeGuard` implements the same keyword policy as the Python example:
- blocks content containing `secret-project`
- redacts content containing `internal-ref`

## Files

| File | Purpose |
|------|---------|
| `main.go` | `DetectorService` v1 implementation + `main()` |
| `go.mod` | Module + grpc/protobuf dependencies |
| `proto/detector/v1/detector.proto` | Contract source (same as gateway `proto/`) |
| `gen_proto.sh` | Stub generation (protoc + protoc-gen-go + protoc-gen-go-grpc) |

## Build & run

```bash
# 1. install protoc plugins
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
export PATH="$PATH:$(go env GOPATH)/bin"

# 2. generate stubs (writes proto/detector/v1/*.pb.go)
./gen_proto.sh

# 3. fetch deps and run
go mod tidy
go run . --port 50051
```

## Configure the gateway

```yaml
pipeline:
  detectors:
    input:
      - name: acme_go_guard
        type: grpc
        enabled: true
        config:
          endpoint: "localhost:50051"
```

## Notes

- `HealthCheck` returns `serving` once the process is up (the gateway checks
  health before `Initialize`, DESIGN.md §7.3.3).
- `DetectResponse.Details` is `google.protobuf.Struct`; in Go, build it with
  `structpb` and set it via `Details: structpb.NewStruct(map[string]any{...})`.
