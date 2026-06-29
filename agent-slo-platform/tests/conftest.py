"""Test fixtures."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from agent_slo.api import app, get_db
from agent_slo.models import (
    Agent,
    Base,
    Metric,
    ServiceLevelIndicator,
    ServiceLevelObjective,
    Tenant,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[tuple, None]:
    """Fresh in-memory SQLite database per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield engine, SessionLocal

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(db) -> AsyncGenerator[AsyncSession, None]:
    engine, SessionLocal = db
    async with SessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant(session: AsyncSession) -> Tenant:
    t = Tenant(slug="acme-corp", name="Acme Corp")
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@pytest_asyncio.fixture
async def agent(session: AsyncSession, tenant: Tenant) -> Agent:
    a = Agent(
        tenant_id=tenant.id,
        environment="production",
        name="onboarding-agent",
        framework="openai-agents",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


@pytest_asyncio.fixture
async def sli_task_success(session: AsyncSession, tenant: Tenant) -> ServiceLevelIndicator:
    sli = ServiceLevelIndicator(
        tenant_id=tenant.id,
        name="task_success_rate",
        metric_type="ratio",
        source="otel_attribute",
        config={"numerator_attr": "gen_ai.eval.success", "denominator_attr": "gen_ai.eval.total"},
    )
    session.add(sli)
    await session.commit()
    await session.refresh(sli)
    return sli


@pytest_asyncio.fixture
async def slo_task_success(
    session: AsyncSession,
    tenant: Tenant,
    sli_task_success: ServiceLevelIndicator,
) -> ServiceLevelObjective:
    slo = ServiceLevelObjective(
        tenant_id=tenant.id,
        sli_id=sli_task_success.id,
        name="task-success-rate",
        target=0.95,
        comparator="gt",
        window="7d",
        burn_rate_alert_thresholds=[
            {"threshold": 0.02, "severity": "info"},
            {"threshold": 0.10, "severity": "critical"},
        ],
        labels={"team": "agent-platform"},
    )
    session.add(slo)
    await session.commit()
    await session.refresh(slo)
    return slo


@pytest_asyncio.fixture
async def metrics_task_success(
    session: AsyncSession,
    tenant: Tenant,
    agent: Agent,
    sli_task_success: ServiceLevelIndicator,
) -> list[Metric]:
    now = datetime.now(timezone.utc)
    metrics = []
    for i in range(100):
        # 95 successes, 5 failures
        value = 1.0 if i < 95 else 0.0
        metrics.append(Metric(
            tenant_id=tenant.id,
            agent_id=agent.id,
            sli_id=sli_task_success.id,
            timestamp=now - timedelta(hours=i),
            value=value,
            count=1,
            window_start=now - timedelta(hours=i + 1),
            window_end=now - timedelta(hours=i),
        ))
    session.add_all(metrics)
    await session.commit()
    return metrics
