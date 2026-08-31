"""Immutable request-scoped tenant identity contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TenantIdentitySource = Literal["api_key", "legacy_single_tenant"]


@dataclass(frozen=True, slots=True)
class TenantContext:
    """A secret-free tenant identity snapshot for one admitted request."""

    tenant_id: str
    identity_source: TenantIdentitySource
    contract_version: Literal["1.0"] = "1.0"


LEGACY_TENANT_CONTEXT = TenantContext(
    tenant_id="default",
    identity_source="legacy_single_tenant",
)
