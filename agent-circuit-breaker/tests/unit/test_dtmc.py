from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.dtmc import build_dtmc, predict_risk, _collapse_tool
from circuit_breaker.models import ToolCall

TEST_TENANT = uuid.uuid4()
TEST_AGENT = "agent-1"


@pytest.fixture
def tool_calls_in_session(session: AsyncSession) -> list[ToolCall]:
    """Insert sequential tool calls in a single session and return them."""
    now = datetime.now(timezone.utc)
    calls = [
        ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="read_file", tool_input={}, timestamp=now,
        ),
        ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="write_file", tool_input={}, timestamp=now + timedelta(seconds=1),
        ),
        ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="execute_command", tool_input={}, timestamp=now + timedelta(seconds=2),
        ),
        ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="read_file", tool_input={}, timestamp=now + timedelta(seconds=3),
        ),
        ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="read_file", tool_input={}, timestamp=now + timedelta(seconds=4),
        ),
    ]
    for c in calls:
        session.add(c)
    return calls


class TestCollapseTool:
    def test_known_prefix_maps_to_category(self):
        assert _collapse_tool("delete_file") == "destructive"
        assert _collapse_tool("execute_command") == "execution"
        assert _collapse_tool("query_users") == "data"
        assert _collapse_tool("auth_login") == "identity"

    def test_unknown_tool_returns_other(self):
        assert _collapse_tool("unknown_tool") == "other"
        assert _collapse_tool("random_call") == "other"


class TestBuildDTMC:
    async def test_insufficient_data_returns_error(self, session: AsyncSession):
        result = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        assert result.get("error") == "insufficient_data"
        assert result["transitions"] == 0

    async def test_builds_matrix_from_sequence(self, session: AsyncSession, tool_calls_in_session):
        result = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        assert result["matrix"] is not None
        assert result["transitions"] >= 4
        assert len(result["states"]) > 0

    async def test_row_sums_to_one(self, session: AsyncSession, tool_calls_in_session):
        result = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        matrix = result["matrix"]
        for i in range(result["n"]):
            row_sum = matrix[i].sum()
            assert abs(row_sum - 1.0) < 1e-10, f"Row {i} sums to {row_sum}"

    async def test_blocked_transitions_to_blocked_state(self, session: AsyncSession):
        now = datetime.now(timezone.utc)
        session.add(ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="read_file", tool_input={}, timestamp=now,
        ))
        blocked = ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="delete_file", tool_input={}, timestamp=now + timedelta(seconds=1),
            blocked=True, decision="block",
        )
        session.add(blocked)
        session.add(ToolCall(
            tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-1",
            tool_name="read_file", tool_input={}, timestamp=now + timedelta(seconds=2),
        ))
        await session.flush()

        result = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        matrix = result["matrix"]
        blocked_idx = result["blocked_idx"]
        # blocked state should be absorbing (self-loop)
        assert matrix[blocked_idx, blocked_idx] == 1.0


class TestPredictRisk:
    async def test_returns_zero_when_no_matrix(self, session: AsyncSession):
        pred = predict_risk({"matrix": None, "transitions": 0, "states": [], "n": 0}, "read_file")
        assert pred["probability"] == 0.0

    async def test_prediction_from_sequence(self, session: AsyncSession, tool_calls_in_session):
        dtmc = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        pred = predict_risk(dtmc, "read_file", steps=5)
        assert 0.0 <= pred["probability"] <= 1.0
        assert 0.0 <= pred["eps"] <= 1.0
        assert pred["ci_low"] <= pred["probability"]
        assert pred["ci_high"] >= pred["probability"]

    async def test_pac_bound_tightens_with_more_data(self, session: AsyncSession):
        now = datetime.now(timezone.utc)
        # Insert many sequential calls to increase transition count
        for i in range(10):
            session.add(ToolCall(
                tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-many",
                tool_name="read_file", tool_input={}, timestamp=now + timedelta(seconds=i),
            ))
        dtmc_few = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        pred_few = predict_risk(dtmc_few, "read_file", steps=3)
        # Flush and add more data
        await session.flush()
        for i in range(10, 110):
            session.add(ToolCall(
                tenant_id=TEST_TENANT, agent_id=TEST_AGENT, session_id="sess-many",
                tool_name="read_file", tool_input={}, timestamp=now + timedelta(seconds=i),
            ))
        await session.flush()
        dtmc_many = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        pred_many = predict_risk(dtmc_many, "read_file", steps=3)
        assert pred_many["eps"] < pred_few["eps"]

    async def test_unknown_current_tool(self, session: AsyncSession, tool_calls_in_session):
        dtmc = await build_dtmc(session, TEST_TENANT, TEST_AGENT, 60)
        pred = predict_risk(dtmc, "nonexistent_tool", steps=5)
        assert pred["probability"] == 0.0
