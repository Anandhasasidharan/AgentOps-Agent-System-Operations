"""State Tracker — maintains windowed agent state for rate limiting and trend analysis."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import AgentState, ToolCall


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _window_key(ts: datetime, window_minutes: int = 5) -> tuple[datetime, datetime]:
    epoch = int(ts.timestamp() // (window_minutes * 60))
    start = datetime.fromtimestamp(epoch * window_minutes * 60, tz=timezone.utc)
    end = start + timedelta(minutes=window_minutes)
    return start, end


async def update_agent_state(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    tool_call: ToolCall,
    timestamp: datetime | None = None,
) -> AgentState:
    ts = timestamp or now_utc()
    window_start, window_end = _window_key(ts)

    stmt = select(AgentState).where(
        AgentState.tenant_id == tenant_id,
        AgentState.agent_id == agent_id,
        AgentState.window_start == window_start,
    )
    result = await session.execute(stmt)
    state = result.scalar_one_or_none()

    if not state:
        state = AgentState(
            tenant_id=tenant_id,
            agent_id=agent_id,
            window_start=window_start,
            window_end=window_end,
        )
        session.add(state)

    # mapped_column default doesn't set Python attr; ensure defaults
    state.call_count = (state.call_count or 0) + 1
    state.unique_tools = state.unique_tools or []
    state.total_tokens = (state.total_tokens or 0) + (tool_call.token_count or 0)
    state.total_cost = (state.total_cost or 0) + (float(tool_call.cost) if tool_call.cost else 0.0)
    state.anomaly_count = (state.anomaly_count or 0) + (
        1 if tool_call.anomaly_score and tool_call.anomaly_score > 0.5 else 0
    )
    state.failure_count = (state.failure_count or 0) + (1 if tool_call.blocked else 0)

    if tool_call.tool_name not in state.unique_tools:
        state.unique_tools = list(set(state.unique_tools + [tool_call.tool_name]))

    max_risk = state.max_risk_score or 0.0
    if tool_call.risk_score and tool_call.risk_score > max_risk:
        state.max_risk_score = tool_call.risk_score

    if tool_call.duration_ms is not None:
        old_avg = state.avg_duration_ms
        if old_avg is not None:
            state.avg_duration_ms = old_avg + (tool_call.duration_ms - old_avg) / min(
                state.call_count, 100
            )
        else:
            state.avg_duration_ms = tool_call.duration_ms

    await session.flush()
    return state
