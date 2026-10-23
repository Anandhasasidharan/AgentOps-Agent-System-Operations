"""The SLO -> lockdown -> block loop, end to end.

This is the flagship closed-loop claim. It failed before M1 because the writer
stored ``max_calls_per_minute`` while the engine read ``max_calls``, the handler
used an async generator as a context manager, and breach events did not carry
an agent id.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.api import handle_slo_breach
from circuit_breaker.models import Policy
from circuit_breaker.proxy import intercept_tool_call


def _breach_message(tenant_id: uuid.UUID, agent_id: str | None) -> SimpleNamespace:
    payload = {}
    if agent_id is not None:
        payload["agent_id"] = agent_id
    data = {
        "tenant_id": str(tenant_id),
        "event_type": "agentops.slo.breach.7d",
        "payload": payload,
    }
    return SimpleNamespace(data=json.dumps(data).encode())


@asynccontextmanager
async def _same_session(session: AsyncSession):
    yield session


@pytest.mark.asyncio
async def test_slo_breach_creates_policy_and_blocks_next_call(session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    agent_id = "checkout-agent"

    await handle_slo_breach(
        _breach_message(tenant_id, agent_id),
        session_factory=lambda: _same_session(session),
    )

    policies = list(
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    assert len(policies) == 1
    policy = policies[0]
    assert policy.name == f"auto-lockdown-{agent_id}"
    assert policy.policy_type == "tool_blocklist"
    assert policy.conditions == {"tools": ["*"], "agent_id": agent_id}
    assert policy.action == "block"

    result = await intercept_tool_call(
        session,
        tenant_id,
        agent_id,
        None,
        tool_name="read_file",
        tool_input={"path": "/tmp/notes.txt"},
    )
    assert result["allowed"] is False
    assert result["decision"] == "block"
    assert result["incident_id"] is not None


@pytest.mark.asyncio
async def test_lockdown_is_scoped_to_the_breaching_agent(session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()

    await handle_slo_breach(
        _breach_message(tenant_id, "agent-a"),
        session_factory=lambda: _same_session(session),
    )

    blocked = await intercept_tool_call(
        session, tenant_id, "agent-a", None, tool_name="read_file", tool_input={}
    )
    allowed = await intercept_tool_call(
        session, tenant_id, "agent-b", None, tool_name="read_file", tool_input={}
    )

    assert blocked["allowed"] is False
    assert allowed["allowed"] is True


@pytest.mark.asyncio
async def test_lockdown_is_idempotent(session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    agent_id = "agent-a"

    for _ in range(2):
        await handle_slo_breach(
            _breach_message(tenant_id, agent_id),
            session_factory=lambda: _same_session(session),
        )

    policies = list(
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    assert len(policies) == 1


@pytest.mark.asyncio
async def test_breach_without_agent_id_does_not_create_a_tenant_wide_policy(
    session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()

    await handle_slo_breach(
        _breach_message(tenant_id, None),
        session_factory=lambda: _same_session(session),
    )

    policies = list(
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    assert policies == []
