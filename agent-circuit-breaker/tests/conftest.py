"""Test fixtures for circuit breaker."""

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

from circuit_breaker.api import app, get_tenant
from circuit_breaker.models import Base, Policy, ToolCall


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
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def override_get_tenant() -> uuid.UUID:
        return TEST_TENANT_ID

    app.dependency_overrides[get_tenant] = override_get_tenant
    app.dependency_overrides.clear()
    app.dependency_overrides[get_tenant] = override_get_tenant

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_policy(session: AsyncSession) -> Policy:
    p = Policy(
        tenant_id=TEST_TENANT_ID,
        name="block-dangerous-tools",
        policy_type="tool_blocklist",
        conditions={"tools": ["delete_file", "execute_command", "drop_table"]},
        action="block",
        priority=10,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


@pytest_asyncio.fixture
async def rate_limit_policy(session: AsyncSession) -> Policy:
    p = Policy(
        tenant_id=TEST_TENANT_ID,
        name="rate-limit-100",
        policy_type="rate_limit",
        conditions={"max_calls": 100},
        action="block",
        priority=5,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p
