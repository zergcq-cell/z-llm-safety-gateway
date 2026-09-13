"""Payload-free observation identity usable by the Flow core."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")


class ObservationScope(str, Enum):
    """The trusted provenance category for an observation event."""

    TENANT = "tenant"
    LEGACY = "legacy"
    UNATTRIBUTED = "unattributed"
    POLICY = "policy"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class TenantObservationContext:
    """Validated identity projection with no request payload or credentials."""

    scope: ObservationScope
    tenant_id: str | None = None
    policy_id: str | None = None
    contract_version: Literal["1.0"] = "1.0"

    def __post_init__(self) -> None:
        if self.scope is ObservationScope.TENANT:
            valid = self.tenant_id is not None and self.policy_id is not None
        elif self.scope is ObservationScope.POLICY:
            valid = self.tenant_id is None and self.policy_id is not None
        else:
            valid = self.tenant_id is None and self.policy_id is None
        if not valid or any(
            value is not None and _ID_PATTERN.fullmatch(value) is None
            for value in (self.tenant_id, self.policy_id)
        ):
            raise ValueError("tenant_context_invalid")

    @classmethod
    def legacy(cls) -> TenantObservationContext:
        return cls(scope=ObservationScope.LEGACY)

    @classmethod
    def system(cls) -> TenantObservationContext:
        return cls(scope=ObservationScope.SYSTEM)

    @classmethod
    def unattributed(cls) -> TenantObservationContext:
        return cls(scope=ObservationScope.UNATTRIBUTED)

    @classmethod
    def policy(cls, policy_id: str) -> TenantObservationContext:
        return cls(scope=ObservationScope.POLICY, policy_id=policy_id)
