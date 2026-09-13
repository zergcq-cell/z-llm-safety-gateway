"""Stable, secret-free tenant failure outcomes and protocol mapping."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureKind(str, Enum):
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    INITIALIZATION_FAILED = "initialization_failed"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    ISOLATION_VIOLATION = "isolation_violation"


@dataclass(frozen=True, slots=True)
class FailureOutcome:
    kind: FailureKind
    code: str
    retryable: bool = False

    @classmethod
    def from_kind(cls, kind: FailureKind) -> FailureOutcome:
        codes = {
            FailureKind.CAPACITY_EXHAUSTED: "tenant_resource_exhausted",
            FailureKind.TIMEOUT: "tenant_request_timeout",
            FailureKind.CANCELLED: "tenant_request_cancelled",
            FailureKind.INITIALIZATION_FAILED: "tenant_runtime_unavailable",
            FailureKind.PROVIDER_UNAVAILABLE: "provider_unavailable",
            FailureKind.ISOLATION_VIOLATION: "tenant_isolation_violation",
        }
        return cls(
            kind,
            codes[kind],
            kind in {FailureKind.CAPACITY_EXHAUSTED, FailureKind.PROVIDER_UNAVAILABLE},
        )

    def http_status(self) -> int:
        return {
            FailureKind.CAPACITY_EXHAUSTED: 429,
            FailureKind.TIMEOUT: 504,
            FailureKind.CANCELLED: 499,
            FailureKind.INITIALIZATION_FAILED: 503,
            FailureKind.PROVIDER_UNAVAILABLE: 503,
            FailureKind.ISOLATION_VIOLATION: 500,
        }[self.kind]

    def public_body(self) -> dict[str, object]:
        return {"error": {"message": self.code, "type": "tenant_failure", "code": self.code}}
