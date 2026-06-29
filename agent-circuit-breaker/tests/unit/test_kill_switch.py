"""Tests for the Kill Switch."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.kill_switch import (
    activate_kill_switch,
    check_kill_switch,
    get_kill_switch_status,
    release_kill_switch,
)


@pytest.mark.asyncio
async def test_activate_and_check(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    ks = await activate_kill_switch(session, tenant_id, agent_id, "Testing", "manual")
    assert ks.active is True

    is_killed = await check_kill_switch(session, tenant_id, agent_id)
    assert is_killed is True


@pytest.mark.asyncio
async def test_release_kill_switch(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    await activate_kill_switch(session, tenant_id, agent_id, "Testing", "manual")
    await release_kill_switch(session, tenant_id, agent_id)

    is_killed = await check_kill_switch(session, tenant_id, agent_id)
    assert is_killed is False


@pytest.mark.asyncio
async def test_no_kill_switch_by_default(session):
    tenant_id = uuid.uuid4()
    is_killed = await check_kill_switch(session, tenant_id, "unknown-agent")
    assert is_killed is False


@pytest.mark.asyncio
async def test_get_kill_switch_status(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    await activate_kill_switch(session, tenant_id, agent_id, "High risk score", "risk_engine")
    status = await get_kill_switch_status(session, tenant_id, agent_id)

    assert status["active"] is True
    assert status["reason"] == "High risk score"
    assert status["triggered_by"] == "risk_engine"


@pytest.mark.asyncio
async def test_get_kill_switch_status_inactive(session):
    tenant_id = uuid.uuid4()
    status = await get_kill_switch_status(session, tenant_id, "no-such-agent")
    assert status["active"] is False
