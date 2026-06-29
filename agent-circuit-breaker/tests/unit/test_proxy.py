"""Tests for the Circuit Breaker Proxy."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.models import Policy
from circuit_breaker.proxy import intercept_tool_call


@pytest.mark.asyncio
async def test_intercept_allows_safe_tool(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    result = await intercept_tool_call(
        session, tenant_id, agent_id, None,
        tool_name="read_file",
        tool_input={"path": "/tmp/notes.txt"},
        duration_ms=50,
        token_count=10,
    )
    assert result["allowed"] is True
    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_intercept_blocks_blocklisted_tool(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    policy = Policy(
        tenant_id=tenant_id,
        name="block-delete",
        policy_type="tool_blocklist",
        conditions={"tools": ["delete_file"]},
        action="block",
        priority=10,
    )
    session.add(policy)
    await session.commit()

    result = await intercept_tool_call(
        session, tenant_id, agent_id, None,
        tool_name="delete_file",
        tool_input={"path": "/etc/passwd"},
    )
    assert result["allowed"] is False
    assert result["decision"] == "block"
    assert result["incident_id"] is not None


@pytest.mark.asyncio
async def test_intercept_kill_switch_active(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    from circuit_breaker.kill_switch import activate_kill_switch
    await activate_kill_switch(session, tenant_id, agent_id, "Manual kill", "manual")

    result = await intercept_tool_call(
        session, tenant_id, agent_id, None,
        tool_name="read_file",
        tool_input={},
    )
    assert result["allowed"] is False
    assert result["decision"] == "kill"


@pytest.mark.asyncio
async def test_intercept_returns_risk_and_anomaly_scores(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    result = await intercept_tool_call(
        session, tenant_id, agent_id, "session-1",
        tool_name="search",
        tool_input={"query": "hello"},
        duration_ms=100,
        token_count=50,
    )
    assert "risk_score" in result
    assert "anomaly_score" in result
    assert result["tool_call_id"] is not None


@pytest.mark.asyncio
async def test_intercept_persists_tool_call(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    result = await intercept_tool_call(
        session, tenant_id, agent_id, None,
        tool_name="search",
        tool_input={"q": "test"},
    )

    from circuit_breaker.models import ToolCall
    from sqlalchemy import select
    stmt = select(ToolCall).where(ToolCall.id == result["tool_call_id"])
    r = await session.execute(stmt)
    tc = r.scalar_one_or_none()
    assert tc is not None
    assert tc.tool_name == "search"
    assert tc.tenant_id == tenant_id
