"""Scheduled enforcement must evaluate tenants without dashboard polling."""

from unittest.mock import AsyncMock

from agent_slo import api


async def test_scheduler_evaluates_tenants(db, tenant, monkeypatch):
    _, factory = db
    monkeypatch.setattr(api, "AsyncSessionLocal", factory)
    evaluate = AsyncMock()
    monkeypatch.setattr(api, "status", evaluate)
    await api.evaluate_tenants_once()
    evaluate.assert_awaited_once()
    assert evaluate.call_args.kwargs["tenant"].id == tenant.id
    assert evaluate.call_args.kwargs["agent_id"] is None


async def test_scheduler_continues_after_tenant_failure(db, tenant, monkeypatch):
    from agentops_core.base import Tenant

    _, factory = db
    async with factory() as session:
        session.add(Tenant(slug="second", name="Second"))
        await session.commit()
    monkeypatch.setattr(api, "AsyncSessionLocal", factory)
    evaluate = AsyncMock(side_effect=[RuntimeError("temporary failure"), []])
    monkeypatch.setattr(api, "status", evaluate)
    await api.evaluate_tenants_once()
    assert evaluate.await_count == 2


async def test_evaluation_loop_retries_and_honors_interval(monkeypatch):
    import asyncio
    import pytest

    evaluate = AsyncMock(side_effect=RuntimeError("database temporarily unavailable"))
    sleep = AsyncMock(side_effect=asyncio.CancelledError)
    monkeypatch.setattr(api, "evaluate_tenants_once", evaluate)
    monkeypatch.setattr(api.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await api.evaluation_loop()
    evaluate.assert_awaited_once()
    sleep.assert_awaited_once_with(api.settings.slo_evaluation_interval_seconds)


async def test_lifespan_provisions_durability_and_closes_resources(monkeypatch):
    from unittest.mock import MagicMock

    engine = MagicMock()
    engine.begin.return_value.__aenter__.return_value.run_sync = AsyncMock()
    engine.dispose = AsyncMock()
    nc = AsyncMock()
    provision = AsyncMock()
    monkeypatch.setattr(api, "engine", engine)
    monkeypatch.setattr(api, "create_nats_client", AsyncMock(return_value=nc))
    monkeypatch.setattr(api, "ensure_breach_stream", provision)
    monkeypatch.setattr(api.settings, "slo_evaluation_interval_seconds", 0)
    async with api.lifespan(api.app):
        provision.assert_awaited_once_with(nc)
    nc.close.assert_awaited_once()
    engine.dispose.assert_awaited_once()


async def test_configured_broker_failure_prevents_startup(monkeypatch):
    import pytest
    from unittest.mock import MagicMock

    engine = MagicMock()
    engine.begin.return_value.__aenter__.return_value.run_sync = AsyncMock()
    engine.dispose = AsyncMock()
    monkeypatch.setattr(api, "engine", engine)
    monkeypatch.setattr(api, "create_nats_client", AsyncMock(return_value=None))
    monkeypatch.setattr(api.settings, "nats_url", "nats://unavailable:4222")
    with pytest.raises(RuntimeError, match="Configured NATS is unavailable"):
        async with api.lifespan(api.app):
            pytest.fail("An unavailable configured broker must prevent startup")
    engine.dispose.assert_awaited_once()
