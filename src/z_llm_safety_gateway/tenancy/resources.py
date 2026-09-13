"""Bounded per-tenant resource budgets and leases."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Literal

ResourceKind = Literal["request", "stream", "background"]


class TenantResourceError(RuntimeError):
    """Base class for explicit tenant resource failures."""

    code = "tenant_resource_error"


class TenantResourceExhausted(TenantResourceError):  # noqa: N818
    code = "tenant_resource_exhausted"


class TenantResourceTimeout(TenantResourceError):  # noqa: N818
    code = "tenant_resource_timeout"


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_concurrency: int = 16
    queue_limit: int = 32
    request_timeout_seconds: float = 120.0
    max_streams: int = 16
    max_background_tasks: int = 32

    def __post_init__(self) -> None:
        if not 1 <= self.max_concurrency <= 4096:
            raise ValueError("invalid_resource_max_concurrency")
        if not 0 <= self.queue_limit <= 4096:
            raise ValueError("invalid_resource_queue_limit")
        if not 0 < self.request_timeout_seconds <= 3600:
            raise ValueError("invalid_resource_request_timeout")
        if not 1 <= self.max_streams <= 4096:
            raise ValueError("invalid_resource_max_streams")
        if not 0 <= self.max_background_tasks <= 4096:
            raise ValueError("invalid_resource_background_tasks")


@dataclass(frozen=True, slots=True)
class ResourceSnapshot:
    tenant_id: str
    budget: ResourceBudget
    deadline: float


class _TenantGate:
    def __init__(self, budget: ResourceBudget) -> None:
        self.budget = budget
        self.semaphore = asyncio.Semaphore(budget.max_concurrency)
        self.waiters = 0
        self.active = 0
        self.streams = 0
        self.background = 0
        self.lock = asyncio.Lock()

    async def acquire(
        self, timeout: float | None = None, kind: ResourceKind = "request"
    ) -> ResourceLease:
        async with self.lock:
            if kind not in {"request", "stream", "background"}:
                raise ValueError("invalid_resource_kind")
            if self.active + self.waiters >= self.budget.max_concurrency + self.budget.queue_limit:
                raise TenantResourceExhausted(TenantResourceExhausted.code)
            if kind == "stream" and self.streams >= self.budget.max_streams:
                raise TenantResourceExhausted("tenant_streams_exhausted")
            if kind == "background" and self.background >= self.budget.max_background_tasks:
                raise TenantResourceExhausted("tenant_background_tasks_exhausted")
            self.waiters += 1
        try:
            try:
                if timeout is None:
                    await self.semaphore.acquire()
                else:
                    await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise TenantResourceTimeout(TenantResourceTimeout.code) from exc
            async with self.lock:
                self.active += 1
                if kind == "stream":
                    self.streams += 1
                elif kind == "background":
                    self.background += 1
            return ResourceLease(self, kind)
        finally:
            async with self.lock:
                self.waiters -= 1

    async def release(self, kind: ResourceKind) -> None:
        async with self.lock:
            if self.active > 0:
                self.active -= 1
                if kind == "stream" and self.streams > 0:
                    self.streams -= 1
                elif kind == "background" and self.background > 0:
                    self.background -= 1
                self.semaphore.release()


class ResourceLease:
    def __init__(self, gate: _TenantGate, kind: ResourceKind = "request") -> None:
        self._gate = gate
        self._kind = kind
        self._released = False

    async def __aenter__(self) -> ResourceLease:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.release()

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._gate.release(self._kind)


class TenantResourceManager:
    def __init__(self, budgets: dict[str, ResourceBudget] | None = None) -> None:
        self._budgets = dict(budgets or {})
        self._gates: dict[str, _TenantGate] = {}
        self._lock = asyncio.Lock()

    async def snapshot(self, tenant_id: str) -> ResourceSnapshot:
        budget = self._budgets.get(tenant_id, ResourceBudget())
        return ResourceSnapshot(tenant_id, budget, monotonic() + budget.request_timeout_seconds)

    async def acquire(
        self, snapshot: ResourceSnapshot, kind: ResourceKind = "request"
    ) -> ResourceLease:
        async with self._lock:
            gate = self._gates.get(snapshot.tenant_id)
            if gate is None:
                gate = self._gates[snapshot.tenant_id] = _TenantGate(snapshot.budget)
        remaining = snapshot.deadline - monotonic()
        if remaining <= 0:
            raise TenantResourceTimeout(TenantResourceTimeout.code)
        return await gate.acquire(remaining, kind)

    async def stats(self, tenant_id: str) -> dict[str, int]:
        async with self._lock:
            gate = self._gates.get(tenant_id)
        if gate is None:
            return {"active": 0, "waiters": 0, "streams": 0, "background": 0}
        async with gate.lock:
            return {
                "active": gate.active,
                "waiters": gate.waiters,
                "streams": gate.streams,
                "background": gate.background,
            }
