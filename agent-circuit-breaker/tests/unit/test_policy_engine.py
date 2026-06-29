"""Tests for the Policy Engine."""

from __future__ import annotations

import uuid

import pytest

from circuit_breaker.models import Policy, ToolCall
from circuit_breaker.policy_engine import evaluate_policies, load_policies


@pytest.mark.asyncio
async def test_tool_blocklist(session, sample_policy):
    tool_call = ToolCall(
        tenant_id=sample_policy.tenant_id,
        agent_id="test-agent",
        tool_name="delete_file",
        tool_input={"path": "/tmp/test"},
    )
    decision = await evaluate_policies(session, sample_policy.tenant_id, tool_call)
    assert not decision.allowed
    assert decision.action == "block"
    assert "blocklist" in decision.reason


@pytest.mark.asyncio
async def test_tool_allowlist(session):
    policy = Policy(
        tenant_id=uuid.uuid4(),
        name="allow-read-only",
        policy_type="tool_allowlist",
        conditions={"tools": ["read_file", "list_files", "search"]},
        action="block",
        priority=10,
    )
    session.add(policy)
    await session.commit()

    # send_email is NOT in the allowlist -> blocked
    tool_call = ToolCall(
        tenant_id=policy.tenant_id,
        agent_id="test-agent",
        tool_name="send_email",
    )
    decision = await evaluate_policies(session, policy.tenant_id, tool_call)
    assert not decision.allowed
    assert decision.action == "block"

    # read_file IS in the allowlist -> allowed
    tool_call2 = ToolCall(
        tenant_id=policy.tenant_id,
        agent_id="test-agent",
        tool_name="read_file",
    )
    decision2 = await evaluate_policies(session, policy.tenant_id, tool_call2)
    assert decision2.allowed


@pytest.mark.asyncio
async def test_rate_limit(session, rate_limit_policy):
    tool_call = ToolCall(
        tenant_id=rate_limit_policy.tenant_id,
        agent_id="test-agent",
        tool_name="search",
    )
    # Under limit -> allowed
    decision = await evaluate_policies(
        session, rate_limit_policy.tenant_id, tool_call,
        windowed_stats={"call_count": 50},
    )
    assert decision.allowed

    # Over limit -> blocked
    decision2 = await evaluate_policies(
        session, rate_limit_policy.tenant_id, tool_call,
        windowed_stats={"call_count": 150},
    )
    assert not decision2.allowed


@pytest.mark.asyncio
async def test_risk_threshold(session):
    policy = Policy(
        tenant_id=uuid.uuid4(),
        name="max-risk-0.8",
        policy_type="risk_threshold",
        conditions={"max_risk_score": 0.8},
        action="block",
    )
    session.add(policy)
    await session.commit()

    tc = ToolCall(tenant_id=policy.tenant_id, agent_id="a", tool_name="t", risk_score=0.9)
    decision = await evaluate_policies(session, policy.tenant_id, tc)
    assert not decision.allowed

    tc2 = ToolCall(tenant_id=policy.tenant_id, agent_id="a", tool_name="t", risk_score=0.5)
    decision2 = await evaluate_policies(session, policy.tenant_id, tc2)
    assert decision2.allowed


@pytest.mark.asyncio
async def test_anomaly_threshold(session):
    policy = Policy(
        tenant_id=uuid.uuid4(),
        name="max-anomaly-0.7",
        policy_type="anomaly_threshold",
        conditions={"max_anomaly_score": 0.7},
        action="block",
    )
    session.add(policy)
    await session.commit()

    tc = ToolCall(tenant_id=policy.tenant_id, agent_id="a", tool_name="t", anomaly_score=0.9)
    decision = await evaluate_policies(session, policy.tenant_id, tc)
    assert not decision.allowed


@pytest.mark.asyncio
async def test_reasoning_loop_detection(session):
    policy = Policy(
        tenant_id=uuid.uuid4(),
        name="reasoning-loop-guard",
        policy_type="reasoning_loop",
        conditions={"max_consecutive_same_tool": 5},
        action="block",
    )
    session.add(policy)
    await session.commit()

    tc = ToolCall(tenant_id=policy.tenant_id, agent_id="a", tool_name="search")
    decision = await evaluate_policies(
        session, policy.tenant_id, tc,
        windowed_stats={"consecutive_same_tool": 10},
    )
    assert not decision.allowed


@pytest.mark.asyncio
async def test_no_policies_allows(session):
    tc = ToolCall(
        tenant_id=uuid.uuid4(),
        agent_id="test-agent",
        tool_name="any_tool",
    )
    decision = await evaluate_policies(session, tc.tenant_id, tc)
    assert decision.allowed


@pytest.mark.asyncio
async def test_policy_priority_order(session):
    # Lower priority first, higher priority wins
    low = Policy(
        tenant_id=uuid.uuid4(),
        name="low-priority-allow",
        policy_type="tool_allowlist",
        conditions={"tools": ["*"]},
        action="allow",
        priority=0,
    )
    high = Policy(
        tenant_id=low.tenant_id,
        name="high-priority-block-all",
        policy_type="tool_blocklist",
        conditions={"tools": ["*"]},
        action="block",
        priority=100,
    )
    session.add_all([low, high])
    await session.commit()

    tc = ToolCall(tenant_id=low.tenant_id, agent_id="a", tool_name="anything")
    decision = await evaluate_policies(session, low.tenant_id, tc)
    assert not decision.allowed
    assert "high-priority" in decision.reason
