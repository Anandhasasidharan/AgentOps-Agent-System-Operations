"""Circuit Breaker Proxy — the main orchestration layer.

Intercepts tool calls, runs them through the engines, and returns a decision.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from agentops_core.telemetry import emit_tool_call_span
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.anomaly_engine import compute_anomaly_score
from circuit_breaker.config import Settings
from circuit_breaker.incident_engine import create_incident
from circuit_breaker.kill_switch import check_kill_switch
from circuit_breaker.models import ToolCall
from circuit_breaker.policy_engine import PolicyDecision, evaluate_policies, load_policies
from circuit_breaker.risk_engine import score_tool_call
from circuit_breaker.state_tracker import update_agent_state

settings = Settings()


async def intercept_tool_call(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    session_id: str | None,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any] | None = None,
    duration_ms: float | None = None,
    token_count: int | None = None,
    cost: float | None = None,
    tenant_slug: str | None = None,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc)

    tool_call = ToolCall(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        duration_ms=duration_ms,
        token_count=token_count,
        cost=cost,
        timestamp=ts,
    )

    # 1. Check kill switch
    kill_active = await check_kill_switch(session, tenant_id, agent_id)
    if kill_active:
        tool_call.blocked = True
        tool_call.decision = "kill"
        tool_call.decision_reason = "Agent is under active kill switch"
        session.add(tool_call)
        await session.flush()

        await create_incident(
            session,
            tenant_id,
            agent_id,
            session_id,
            severity="critical",
            category="kill_switch",
            message=f"Tool call blocked: agent {agent_id} is killed",
            details={"tool_name": tool_name, "kill_switch_active": True},
            action_taken="kill",
            tool_call_id=tool_call.id,
        )
        await session.commit()
        return _build_response(tool_call)

    # 2. Score risk
    risk_score, risk_details = await score_tool_call(
        session, tenant_id, agent_id, tool_name, tool_input
    )
    tool_call.risk_score = risk_score

    # 3. Detect anomalies
    anomaly_score, anomaly_details = await compute_anomaly_score(
        session, tenant_id, agent_id, tool_call
    )
    tool_call.anomaly_score = anomaly_score
    tool_call.is_suspicious = anomaly_score > 0.5

    # 4. Evaluate policies
    windowed_stats = await _get_windowed_stats(session, tenant_id, agent_id)
    policies = await load_policies(session, tenant_id)
    decision: PolicyDecision = await evaluate_policies(
        session, tenant_id, tool_call, policies, windowed_stats
    )

    tool_call.decision = decision.action
    tool_call.decision_reason = decision.reason

    incident_id = None
    if not decision.allowed:
        tool_call.blocked = True
        severity = "critical" if decision.action == "kill" else "warning"
        incident = await create_incident(
            session,
            tenant_id,
            agent_id,
            session_id,
            severity=severity,
            category="policy_violation",
            message=decision.reason or f"Blocked by policy: {decision.policy_name}",
            details={
                "tool_name": tool_name,
                "risk_score": risk_score,
                "anomaly_score": anomaly_score,
                "policy_name": decision.policy_name,
                "policy_action": decision.action,
            },
            action_taken=decision.action,
            tool_call_id=tool_call.id,
        )
        incident_id = incident.id

    # 5. Update agent state
    await update_agent_state(session, tenant_id, agent_id, tool_call, ts)

    session.add(tool_call)
    await session.commit()
    await session.refresh(tool_call)

    result = _build_response(tool_call)
    result["incident_id"] = incident_id
    result["risk_score"] = risk_score
    result["anomaly_score"] = anomaly_score

    asyncio.ensure_future(
        emit_tool_call_span(
            endpoint=settings.otel_exporter_endpoint,
            tenant_slug=tenant_slug or "",
            agent_id=agent_id,
            tool_name=tool_name,
            blocked=tool_call.blocked,
            duration_ms=duration_ms,
            token_count=token_count,
            risk_score=risk_score,
        )
    )
    return result


async def _get_windowed_stats(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
) -> dict[str, Any]:
    from datetime import timedelta

    from sqlalchemy import select

    from circuit_breaker.models import ToolCall

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    stmt = (
        select(ToolCall)
        .where(
            ToolCall.tenant_id == tenant_id,
            ToolCall.agent_id == agent_id,
            ToolCall.timestamp >= cutoff,
        )
        .order_by(ToolCall.timestamp.desc())
    )
    result = await session.execute(stmt)
    calls = list(result.scalars().all())

    tool_sequence = [c.tool_name for c in calls]
    consecutive = 0
    if len(tool_sequence) >= 2:
        for i in range(len(tool_sequence) - 1, 0, -1):
            if tool_sequence[i] == tool_sequence[i - 1]:
                consecutive += 1
            else:
                break

    return {
        "call_count": len(calls),
        "total_tokens": sum(c.token_count or 0 for c in calls),
        "total_cost": sum(float(c.cost or 0) for c in calls),
        "consecutive_same_tool": consecutive,
        "tool_sequence": tool_sequence,
    }


def _build_response(tool_call: ToolCall) -> dict[str, Any]:
    return {
        "allowed": not tool_call.blocked,
        "decision": tool_call.decision or "allow",
        "reason": tool_call.decision_reason,
        "risk_score": tool_call.risk_score,
        "anomaly_score": tool_call.anomaly_score,
        "tool_call_id": tool_call.id,
        "incident_id": None,
    }
