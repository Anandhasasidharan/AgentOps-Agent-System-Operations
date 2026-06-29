"""Test fixtures for Chaos Toolkit."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from chaos_toolkit.api import app, get_tenant
from chaos_toolkit.db import get_db
from chaos_toolkit.models import Base, Scenario


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[tuple, None]:
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


TEST_TENANT_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_tenant() -> uuid.UUID:
        return TEST_TENANT_ID

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_tenant] = override_get_tenant
    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_scenario(session: AsyncSession) -> Scenario:
    s = Scenario(
        tenant_id=TEST_TENANT_ID,
        name="llm-timeout-test",
        target_type="llm",
        failure_mode="timeout",
        config={"params": {"delay_seconds": 0.01}},
        expected_behavior="graceful_degradation",
        agent_should_survive=True,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


@pytest_asyncio.fixture
async def sample_tool_scenario(session: AsyncSession) -> Scenario:
    s = Scenario(
        tenant_id=TEST_TENANT_ID,
        name="tool-crash-test",
        target_type="tool",
        failure_mode="crash",
        config={"params": {}},
        expected_behavior="error_handled",
        agent_should_survive=True,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s
