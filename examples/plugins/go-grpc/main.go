// Package main implements the z LLM Safety Gateway DetectorService v1
// (proto/detector/v1/detector.proto) as a Go gRPC sidecar detector.
//
// Build & run:
//
//	# 1. generate stubs (requires protoc + protoc-gen-go + protoc-gen-go-grpc)
//	./gen_proto.sh
//	# 2. download dependencies
//	go mod tidy
//	# 3. run the sidecar
//	go run . --port 50051
//
// Then configure the gateway with:
//
//	pipeline:
//	  detectors:
//	    input:
//	      - name: acme_go_guard
//	        type: grpc
//	        enabled: true
//	        config:
//	          endpoint: "localhost:50051"
//
// NOTE: This example is provided as reference source. It was authored without
// a Go toolchain in the development environment, so it has not been compiled
// or run there. The lifecycle semantics follow DESIGN.md Section 7.3.3
// (HealthCheck reports "serving" while the process is alive; Initialize
// happens after the first HealthCheck).
package main

import (
	"context"
	"flag"
	"log"
	"net"
	"strconv"
	"strings"

	"google.golang.org/grpc"

	detectorpb "github.com/acme/grpc-guard-example/proto/detector/v1"
)

const (
	blockKeyword  = "secret-project"
	redactKeyword = "internal-ref"
)

type acmeGuard struct {
	detectorpb.UnimplementedDetectorServiceServer
	sensitivity string
	ready       bool
}

func (s *acmeGuard) Initialize(_ context.Context, req *detectorpb.InitializeRequest) (*detectorpb.InitializeResponse, error) {
	s.sensitivity = req.Config["sensitivity"]
	if s.sensitivity == "" {
		s.sensitivity = "medium"
	}
	s.ready = true
	log.Printf("initialized (sensitivity=%s)", s.sensitivity)
	return &detectorpb.InitializeResponse{
		Success: true,
		Info: &detectorpb.DetectorInfo{
			Name:        "acme_go_guard",
			Category:    "custom",
			Description: "Acme Go gRPC sidecar guard (example)",
			Version:     "1.0.0",
		},
	}, nil
}

func (s *acmeGuard) Shutdown(context.Context, *detectorpb.ShutdownRequest) (*detectorpb.ShutdownResponse, error) {
	s.ready = false
	log.Println("shutting down")
	return &detectorpb.ShutdownResponse{Success: true}, nil
}

func (s *acmeGuard) HealthCheck(context.Context, *detectorpb.HealthCheckRequest) (*detectorpb.HealthCheckResponse, error) {
	status := "not_serving"
	if s.ready {
		status = "serving"
	}
	return &detectorpb.HealthCheckResponse{Status: status}, nil
}

func (s *acmeGuard) Detect(_ context.Context, req *detectorpb.DetectRequest) (*detectorpb.DetectResponse, error) {
	content := req.GetContent()
	lowered := strings.ToLower(content)

	if strings.Contains(lowered, blockKeyword) {
		return &detectorpb.DetectResponse{
			DetectorName: "acme_go_guard",
			Category:     "custom",
			Action:       "block",
			Confidence:   0.95,
			RiskLevel:    "high",
			Message:      "blocked keyword '" + blockKeyword + "'",
			Details:      map[string]string{"sensitivity": s.sensitivity},
		}, nil
	}
	if strings.Contains(lowered, redactKeyword) {
		modified := strings.ReplaceAll(content, redactKeyword, strings.Repeat("*", len(redactKeyword)))
		return &detectorpb.DetectResponse{
			DetectorName:    "acme_go_guard",
			Category:        "custom",
			Action:          "modify",
			Confidence:      0.9,
			RiskLevel:       "medium",
			Message:         "redacted keyword",
			ModifiedContent: modified,
		}, nil
	}
	return &detectorpb.DetectResponse{
		DetectorName: "acme_go_guard",
		Category:     "custom",
		Action:       "allow",
		Confidence:   0.0,
		RiskLevel:    "low",
		Message:      "ok",
	}, nil
}

func main() {
	port := flag.Int("port", 50051, "listening port")
	flag.Parse()

	lis, err := net.Listen("tcp", ":"+strconv.Itoa(*port))
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	srv := grpc.NewServer()
	detectorpb.RegisterDetectorServiceServer(srv, &acmeGuard{ready: true})
	log.Printf("acme_go_guard gRPC sidecar listening on :%d", *port)
	if err := srv.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
