"""Configuration contract for bounded tenant metrics."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.config.test_tenancy import _gateway_data
from z_llm_safety_gateway.config.models import GatewayConfig


def test_metric_tenant_ids_are_strict_and_bounded() -> None:
    """TC-TOC-001: A declared tenant allowlist is optional, strict, and bounded."""
    data = _gateway_data(tenant_ids=("acme", "globex"))
    data["observability"] = {"tenancy": {"metric_tenant_ids": ["acme"]}}
    config = GatewayConfig(**data)

    assert config.observability.tenancy.metric_tenant_ids == ("acme",)

    for value in (["missing"], ["acme", "acme"], ["acme", 1], ["acme"] * 33):
        data["observability"] = {"tenancy": {"metric_tenant_ids": value}}
        with pytest.raises(ValidationError, match="tenant_observability_config_invalid"):
            GatewayConfig(**data)


def test_tenant_metric_ids_require_enabled_declared_tenants() -> None:
    """TC-TOC-002: Invalid observation configuration fails before serving requests."""
    data = _gateway_data()
    data["tenancy"]["enabled"] = False
    data["observability"] = {"tenancy": {"metric_tenant_ids": ["acme"]}}

    with pytest.raises(ValidationError, match="tenant_observability_config_invalid"):
        GatewayConfig(**data)


def test_roadmap_records_change_four_delivery() -> None:
    """TC-TOC-004: no roadmap claims delivery before Gate 3."""
    root = Path(__file__).parents[3]
    readme = (root / "README.md").read_text()
    design = (root / "DESIGN.md").read_text()

    assert "all four changes are delivered" in readme
    assert "All four v0.3.0 implementation changes are delivered" in design
