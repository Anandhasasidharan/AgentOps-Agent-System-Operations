"""Tests for the Rollback Engine."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.incident_engine import create_incident
from circuit_breaker.models import ToolCall
from circuit_breaker.rollback_engine import INVERSE_TOOL_MAP, execute_rollback


def test_inverse_tool_map():
    assert INVERSE_TOOL_MAP["create_file"] == "delete_file"
    assert INVERSE_TOOL_MAP["process_payment"] == "refund"
    assert "read_file" not in INVERSE_TOOL_MAP  # no inverse for reads


@pytest.mark.asyncio
async def test_execute_rollback(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    tc = ToolCall(
        tenant_id=tenant_id,
        agent_id=agent_id,
        tool_name="create_file",
        tool_input={"path": "/tmp/test.txt"},
        cost=0.05,
    )
    session.add(tc)
    await session.flush()

    incident = await create_incident(
        session, tenant_id, agent_id, "session-1",
        severity="warning", category="policy_violation",
        message="Test incident",
        details={"tool_name": "create_file"},
        action_taken="block",
        tool_call_id=tc.id,
    )
    await session.flush()

    rollbacks = await execute_rollback(session, incident.id)
    assert len(rollbacks) >= 1

    # Should have a tool call compensation
    comp = [r for r in rollbacks if r.rollback_type == "tool_call_compensation"]
    assert len(comp) >= 1
    assert comp[0].details["compensation_tool"] == "delete_file"

    # Should have a cost refund
    refund = [r for r in rollbacks if r.rollback_type == "cost_refund"]
    assert len(refund) >= 1
    assert refund[0].details["refund_amount"] == "0.05"


@pytest.mark.asyncio
async def test_execute_rollback_no_compensation(session):
    tenant_id = uuid.uuid4()
    agent_id = "test-agent"

    tc = ToolCall(
        tenant_id=tenant_id,
        agent_id=agent_id,
        tool_name="read_file",
        cost=0.0,
    )
    session.add(tc)
    await session.flush()

    incident = await create_incident(
        session, tenant_id, agent_id, None,
        severity="info", category="anomaly",
        message="Test",
        details={},
        action_taken="alert",
        tool_call_id=tc.id,
    )
    await session.flush()

    rollbacks = await execute_rollback(session, incident.id)
    # No compensation (read_file has no inverse), no cost refund (cost is 0)
    # But should still have state_restore
    assert len(rollbacks) >= 1
    state = [r for r in rollbacks if r.rollback_type == "state_restore"]
    assert len(state) >= 1
