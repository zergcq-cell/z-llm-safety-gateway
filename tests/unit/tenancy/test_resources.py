import asyncio

import pytest

from z_llm_safety_gateway.tenancy.failures import FailureKind, FailureOutcome
from z_llm_safety_gateway.tenancy.resources import (
    ResourceBudget,
    TenantResourceExhausted,
    TenantResourceManager,
)


@pytest.mark.asyncio
async def test_tenant_gate_isolated_and_releases() -> None:
    manager = TenantResourceManager({"a": ResourceBudget(max_concurrency=1, queue_limit=0)})
    a = await manager.snapshot("a")
    b = await manager.snapshot("b")
    lease_a = await manager.acquire(a)
    lease_b = await manager.acquire(b)
    assert (await manager.stats("a"))["active"] == 1
    assert (await manager.stats("b"))["active"] == 1
    await lease_a.release()
    await lease_b.release()
    assert (await manager.stats("a"))["active"] == 0


@pytest.mark.asyncio
async def test_queue_limit_returns_stable_exhausted() -> None:
    manager = TenantResourceManager({"a": ResourceBudget(max_concurrency=1, queue_limit=0)})
    snapshot = await manager.snapshot("a")
    lease = await manager.acquire(snapshot)
    with pytest.raises(TenantResourceExhausted, match="tenant_resource_exhausted"):
        await manager.acquire(snapshot)
    await lease.release()


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak() -> None:
    manager = TenantResourceManager({"a": ResourceBudget(max_concurrency=1, queue_limit=1)})
    snapshot = await manager.snapshot("a")
    lease = await manager.acquire(snapshot)
    task = asyncio.create_task(manager.acquire(snapshot))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (await manager.stats("a"))["waiters"] == 0
    await lease.release()


def test_failure_outcome_is_stable_and_secret_free() -> None:
    outcome = FailureOutcome.from_kind(FailureKind.PROVIDER_UNAVAILABLE)
    assert outcome.code == "provider_unavailable"
    assert outcome.http_status() == 503
    assert "error" in outcome.public_body()
    assert "secret" not in repr(outcome).lower()

@pytest.mark.asyncio
async def test_stream_and_background_limits_are_independent() -> None:
    manager = TenantResourceManager(
        {"a": ResourceBudget(max_concurrency=3, max_streams=1, max_background_tasks=1)}
    )
    snapshot = await manager.snapshot("a")
    stream = await manager.acquire(snapshot, "stream")
    with pytest.raises(TenantResourceExhausted, match="tenant_streams_exhausted"):
        await manager.acquire(snapshot, "stream")
    background = await manager.acquire(snapshot, "background")
    with pytest.raises(TenantResourceExhausted, match="tenant_background_tasks_exhausted"):
        await manager.acquire(snapshot, "background")
    await stream.release()
    await background.release()
