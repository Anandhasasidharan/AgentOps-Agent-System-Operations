"""FastAPI application for Agent Circuit Breaker."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.config import Settings
from circuit_breaker.db import AsyncSessionLocal, engine, get_db
from circuit_breaker.incident_engine import create_incident, get_active_incidents, resolve_incident
from circuit_breaker.kill_switch import (
    activate_kill_switch,
    check_kill_switch,
    get_kill_switch_status,
    release_kill_switch,
)
from circuit_breaker.models import (
    AgentState,
    Base,
    Incident,
    KillSwitch,
    Policy,
    RollbackLog,
    ToolCall,
)
from circuit_breaker.policy_engine import evaluate_policies, load_policies
from circuit_breaker.proxy import intercept_tool_call
from circuit_breaker.rollback_engine import execute_rollback
from circuit_breaker.schemas import (
    AgentStatusResponse,
    IncidentOut,
    InterceptResponse,
    KillSwitchOut,
    PolicyCreate,
    PolicyOut,
    ToolCallIn,
    ToolCallOut,
)
from circuit_breaker.state_tracker import update_agent_state

settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Agent Circuit Breaker", version="0.1.0", lifespan=lifespan)

TENANT_HEADER = "X-Tenant-ID"


async def get_tenant(
    x_tenant_id: str = Header(..., alias=TENANT_HEADER),
) -> uuid.UUID:
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant ID (must be UUID)")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── Intercept ────────────────────────────────────────────────────────────────


@app.post("/v1/intercept", response_model=InterceptResponse)
async def intercept(
    data: ToolCallIn,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await intercept_tool_call(
        session=session,
        tenant_id=tenant_id,
        agent_id=data.agent_id,
        session_id=data.session_id,
        tool_name=data.tool_name,
        tool_input=data.tool_input,
        tool_output=data.tool_output,
        duration_ms=data.duration_ms,
        token_count=data.token_count,
        cost=data.cost,
    )
    return result


# ─── Policies ──────────────────────────────────────────────────────────────────


@app.post("/api/v1/policies", response_model=PolicyOut, status_code=201)
async def create_policy(
    data: PolicyCreate,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Policy:
    policy = Policy(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        enabled=data.enabled,
        priority=data.priority,
        policy_type=data.policy_type,
        conditions=data.conditions,
        action=data.action,
        action_config=data.action_config,
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


@app.get("/api/v1/policies", response_model=list[PolicyOut])
async def list_policies(
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Policy]:
    stmt = select(Policy).where(Policy.tenant_id == tenant_id).order_by(Policy.priority.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/policies/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Policy:
    stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
    result = await session.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.delete("/api/v1/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
    result = await session.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await session.delete(policy)
    await session.commit()


# ─── Tool Calls ────────────────────────────────────────────────────────────────


@app.get("/api/v1/tool-calls", response_model=list[ToolCallOut])
async def list_tool_calls(
    tenant_id: uuid.UUID = Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[ToolCall]:
    stmt = select(ToolCall).where(ToolCall.tenant_id == tenant_id)
    if agent_id:
        stmt = stmt.where(ToolCall.agent_id == agent_id)
    stmt = stmt.order_by(ToolCall.timestamp.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ─── Kill Switch ───────────────────────────────────────────────────────────────


@app.post("/api/v1/kill-switch/{agent_id}/activate", response_model=KillSwitchOut)
async def activate_kill(
    agent_id: str,
    reason: str = Query(default="Manual kill switch activation"),
    ttl_seconds: int = Query(default=3600, alias="ttl"),
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> KillSwitch:
    ks = await activate_kill_switch(
        session, tenant_id, agent_id, reason, "manual", ttl_seconds
    )
    await session.commit()
    await session.refresh(ks)
    return ks


@app.post("/api/v1/kill-switch/{agent_id}/release", response_model=KillSwitchOut)
async def release_kill(
    agent_id: str,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ks = await release_kill_switch(session, tenant_id, agent_id)
    if not ks:
        raise HTTPException(status_code=404, detail="No active kill switch for this agent")
    await session.commit()
    await session.refresh(ks)
    return ks


@app.get("/api/v1/kill-switch/{agent_id}")
async def get_kill_status(
    agent_id: str,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await get_kill_switch_status(session, tenant_id, agent_id)


# ─── Incidents ─────────────────────────────────────────────────────────────────


@app.get("/api/v1/incidents", response_model=list[IncidentOut])
async def list_incidents(
    tenant_id: uuid.UUID = Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> list[Incident]:
    return await get_active_incidents(session, tenant_id, agent_id)


@app.post("/api/v1/incidents/{incident_id}/resolve")
async def resolve_incident_endpoint(
    incident_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    incident = await resolve_incident(session, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    await session.commit()
    return {"status": "resolved", "incident_id": str(incident_id)}


@app.post("/api/v1/incidents/{incident_id}/rollback")
async def rollback_incident(
    incident_id: uuid.UUID,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rollbacks = await execute_rollback(session, incident_id)
    await session.commit()
    return {
        "incident_id": str(incident_id),
        "rollback_count": len(rollbacks),
        "rollbacks": [str(r.id) for r in rollbacks],
    }


# ─── Agent Status ──────────────────────────────────────────────────────────────


@app.get("/api/v1/agents/{agent_id}/status", response_model=AgentStatusResponse)
async def agent_status(
    agent_id: str,
    tenant_id: uuid.UUID = Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    is_killed = await check_kill_switch(session, tenant_id, agent_id)

    state_stmt = (
        select(AgentState)
        .where(AgentState.tenant_id == tenant_id, AgentState.agent_id == agent_id)
        .order_by(AgentState.window_start.desc())
        .limit(1)
    )
    state_result = await session.execute(state_stmt)
    state = state_result.scalar_one_or_none()

    active_incidents = await get_active_incidents(session, tenant_id, agent_id)

    calls_stmt = (
        select(ToolCall)
        .where(ToolCall.tenant_id == tenant_id, ToolCall.agent_id == agent_id)
        .order_by(ToolCall.timestamp.desc())
        .limit(20)
    )
    calls_result = await session.execute(calls_stmt)
    recent_calls = [
        {"tool_name": c.tool_name, "decision": c.decision, "blocked": c.blocked, "timestamp": str(c.timestamp)}
        for c in calls_result.scalars().all()
    ]

    return {
        "agent_id": agent_id,
        "is_killed": is_killed,
        "state": state,
        "active_incidents": active_incidents,
        "recent_decisions": recent_calls,
    }
