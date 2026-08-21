"""Compose deployment invariants for the v0.1.1 release."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_development_and_production_compose_have_health_contracts() -> None:
    """TC-DEPL-001: both Compose files expose a gateway healthcheck."""
    for filename in ("docker-compose.yml", "docker-compose.prod.yml"):
        gateway = _yaml(ROOT / filename)["services"]["gateway"]
        healthcheck = " ".join(gateway["healthcheck"]["test"])
        assert "/health" in healthcheck
        assert gateway["restart"] == "unless-stopped"


def test_production_compose_preserves_capacity_and_sidecar_invariants() -> None:
    """TC-DEPL-002: production Compose retains capacity and sidecar wiring."""
    compose = _yaml(ROOT / "docker-compose.prod.yml")
    gateway = compose["services"]["gateway"]
    sidecar = compose["services"]["acme-guard"]

    assert gateway["image"] == "z-safety-gateway:0.1.1"
    assert gateway["deploy"]["replicas"] >= 2
    assert set(gateway["deploy"]["resources"]["limits"]) >= {"cpus", "memory"}
    assert set(gateway["deploy"]["resources"]["reservations"]) >= {"cpus", "memory"}
    assert gateway["depends_on"]["acme-guard"]["condition"] == "service_healthy"
    assert set(gateway["networks"]) & set(sidecar["networks"])
    assert "ACME_API_KEY=${ACME_API_KEY:?ACME_API_KEY must be set}" in gateway["environment"]
    assert (
        "DETECTOR_API_KEY=${ACME_API_KEY:?ACME_API_KEY must be set}"
        in sidecar["environment"]
    )
    assert sidecar["healthcheck"]["test"]
    assert set(sidecar["deploy"]["resources"]["limits"]) >= {"cpus", "memory"}

    mounted_config = ROOT / "config" / "gateway.prod.yaml"
    assert "./config/gateway.prod.yaml:/app/config/gateway.yaml:ro" in gateway["volumes"]
    production_config = _yaml(mounted_config)
    detectors = production_config["pipeline"]["detectors"]["input"]
    acme_guard = next(item for item in detectors if item["name"] == "acme_guard")
    assert acme_guard["type"] == "grpc"
    assert acme_guard["config"]["endpoint"] == "acme-guard:50051"


def test_production_image_installs_grpc_runtime_for_enabled_sidecar() -> None:
    """The production image includes the runtime needed by configured gRPC detectors."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'pip install --no-cache-dir --target=/install ".[grpc]"' in dockerfile


def test_plain_compose_scale_uses_non_conflicting_host_port_range() -> None:
    """A two-replica plain Compose deployment must not bind both replicas to port 8080."""
    gateway = _yaml(ROOT / "docker-compose.prod.yml")["services"]["gateway"]
    assert gateway["ports"] == ["8080-8081:8080"]


def test_production_sidecar_is_buildable_and_audit_volume_matches_config() -> None:
    """The checked-in production example must not rely on a nonexistent image or audit path."""
    compose = _yaml(ROOT / "docker-compose.prod.yml")
    gateway = compose["services"]["gateway"]
    sidecar = compose["services"]["acme-guard"]
    assert sidecar["build"] == {
        "context": ".",
        "dockerfile": "examples/plugins/python-grpc/Dockerfile",
    }
    assert sidecar["image"] == "z-safety-acme-example:1.0.0"
    assert "gateway-logs:/var/log/safety-gateway" in gateway["volumes"]
    production_config = _yaml(ROOT / "config" / "gateway.prod.yaml")
    assert production_config["audit"]["enabled"] is True
    assert production_config["audit"]["file"]["path"] == "/var/log/safety-gateway"
