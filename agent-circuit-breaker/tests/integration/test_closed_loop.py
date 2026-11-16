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
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id))).scalars().all()
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
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id))).scalars().all()
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
        (await session.execute(select(Policy).where(Policy.tenant_id == tenant_id))).scalars().all()
    )
    assert policies == []


@pytest.mark.asyncio
async def test_redelivery_does_not_recreate_released_lockdown(session):
    tenant_id = uuid.uuid4()
    message = _breach_message(tenant_id, "agent-a")
    data = json.loads(message.data)
    data["event_id"] = str(uuid.uuid4())
    message.data = json.dumps(data).encode()
    factory = lambda: _same_session(session)
    await handle_slo_breach(message, session_factory=factory)
    policy = (await session.execute(select(Policy))).scalar_one()
    policy.enabled = False
    await session.commit()
    await handle_slo_breach(message, session_factory=factory)
    policies = list((await session.execute(select(Policy))).scalars())
    assert len(policies) == 1
    assert policies[0].enabled is False


@pytest.mark.asyncio
async def test_failed_lockdown_does_not_commit_receipt(session, monkeypatch):
    from circuit_breaker.models import EnforcementReceipt
    from unittest.mock import AsyncMock

    tenant_id = uuid.uuid4()
    message = _breach_message(tenant_id, "agent-a")
    data = json.loads(message.data)
    data["event_id"] = str(uuid.uuid4())
    message.data = json.dumps(data).encode()
    monkeypatch.setattr(
        "circuit_breaker.api.create_lockdown_policy",
        AsyncMock(side_effect=RuntimeError("write failed")),
    )
    with pytest.raises(RuntimeError, match="write failed"):
        await handle_slo_breach(message, session_factory=lambda: _same_session(session))
    await session.rollback()
    assert list((await session.execute(select(EnforcementReceipt))).scalars()) == []


@pytest.mark.asyncio
async def test_policy_kill_persists_until_release(session):
    from circuit_breaker.kill_switch import check_kill_switch, release_kill_switch

    tenant_id = uuid.uuid4()
    session.add(
        Policy(
            tenant_id=tenant_id,
            name="kill-dangerous",
            policy_type="tool_blocklist",
            conditions={"tools": ["dangerous"]},
            action="kill",
            enabled=True,
        )
    )
    await session.commit()
    first = await intercept_tool_call(session, tenant_id, "agent", None, "dangerous", {})
    assert first["decision"] == "kill"
    assert await check_kill_switch(session, tenant_id, "agent")
    second = await intercept_tool_call(session, tenant_id, "agent", None, "read_file", {})
    assert second["allowed"] is False
    await release_kill_switch(session, tenant_id, "agent")
    await session.commit()
    third = await intercept_tool_call(session, tenant_id, "agent", None, "read_file", {})
    assert third["allowed"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["resolve", "rollback"])
async def test_incident_actions_reject_other_tenants(client, session, action):
    from circuit_breaker.incident_engine import create_incident

    incident = await create_incident(
        session, uuid.uuid4(), "foreign-agent", None, "warning", "audit", "foreign", {}, "block"
    )
    await session.commit()
    response = await client.post(f"/api/v1/incidents/{incident.id}/{action}")
    assert response.status_code == 404
    assert incident.resolved_at is None
    assert not incident.rolled_back


@pytest.mark.asyncio
async def test_rollback_plans_are_visible_and_tenant_scoped(client, session):
    policy = await client.post(
        "/api/v1/policies",
        json={
            "name": "plan-ui",
            "policy_type": "tool_blocklist",
            "conditions": {"tools": ["write_file"]},
            "action": "block",
        },
    )
    assert policy.status_code == 201
    call = await client.post(
        "/v1/intercept",
        json={
            "agent_id": "plan-agent",
            "tool_name": "write_file",
            "tool_input": {"path": "/tmp/never-executed"},
        },
    )
    incident_id = call.json()["incident_id"]
    assert (await client.post(f"/api/v1/incidents/{incident_id}/rollback")).status_code == 200
    plans = await client.get(f"/api/v1/incidents/{incident_id}/rollbacks")
    assert plans.status_code == 200
    assert any(p["type"] == "tool_call_compensation" for p in plans.json())
    assert all(p["status"] == "pending" for p in plans.json())
    from circuit_breaker.incident_engine import create_incident

    foreign = await create_incident(
        session, uuid.uuid4(), "foreign", None, "warning", "audit", "audit", {}, "block"
    )
    await session.commit()
    assert (await client.get(f"/api/v1/incidents/{foreign.id}/rollbacks")).status_code == 404
