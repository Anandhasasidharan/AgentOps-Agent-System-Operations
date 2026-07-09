"""FastAPI application for Agent Circuit Breaker."""

from __future__ import annotations

import asyncio
import json
import logging  # noqa: E402
import uuid
from contextlib import asynccontextmanager
from time import time
from typing import Any

from agentops_core.auth import make_get_tenant
from agentops_core.rate_limiter import add_rate_limiter
from agentops_events import (
    TOPIC_CB_INCIDENT,
    TOPIC_CB_INTERCEPT,
    TOPIC_CB_KILL,
    create_nats_client,
    make_event,
    publish_event,
)
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.config import Settings
from circuit_breaker.db import engine, get_db
from circuit_breaker.incident_engine import get_active_incidents, resolve_incident
from circuit_breaker.kill_switch import (
    activate_kill_switch,
    check_kill_switch,
    get_kill_switch_status,
    release_kill_switch,
)
from circuit_breaker.metrics import (
    add_metrics_route,
    events_dropped_total,
    kill_switches_active,
    policies_total,
    tool_calls_total,
    tool_duration_seconds,
)
from circuit_breaker.models import (
    AgentState,
    Base,
    Incident,
    KillSwitch,
    Policy,
    ToolCall,
)
from circuit_breaker.predictor import get_prediction
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

logger = logging.getLogger(__name__)

settings = Settings()

nats_nc = None
sub_tasks: list[asyncio.Task] = []


async def _pub(event: Any):
    try:
        await publish_event(nats_nc, event)
    except Exception:
        events_dropped_total.labels(reason="publish_failed", service="circuit-breaker").inc()


async def handle_slo_breach(msg):
    try:
        data = json.loads(msg.data.decode())
        payload = data.get("payload", {})
        agent_id = payload.get("agent_id") or data.get("agent_id")
        if not agent_id:
            return
        from circuit_breaker.db import get_db
        async with get_db() as session:
            existing = await session.execute(
                select(Policy).where(
                    Policy.tenant_id == uuid.UUID(data["tenant_id"]),
                    Policy.name == f"auto-lockdown-{agent_id}",
                    Policy.enabled,
                )
            )
            if existing.scalar_one_or_none():
                return
            policy = Policy(
                tenant_id=uuid.UUID(data["tenant_id"]),
                name=f"auto-lockdown-{agent_id}",
                description=f"Auto-tightened after SLO breach for {agent_id}",
                enabled=True,
                priority=100,
                policy_type="rate_limit",
                conditions={"max_calls_per_minute": 5},
                action="block",
            )
            session.add(policy)
            await session.commit()
            logger.info("auto-created lockdown policy for %s after SLO breach", agent_id)
    except Exception:
        logger.exception("error handling SLO breach in CB")


async def subscribe_cross_service():
    if not nats_nc:
        return
    await nats_nc.subscribe("agentops.slo.breach.*", cb=handle_slo_breach)
    logger.info("CB subscribed to agentops.slo.breach.*")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nats_nc
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    nats_nc = await create_nats_client(settings.nats_url)
    task = asyncio.ensure_future(subscribe_cross_service())
    sub_tasks.append(task)
    yield
    for t in sub_tasks:
        t.cancel()
    if nats_nc:
        await nats_nc.close()
    await engine.dispose()


app = FastAPI(title="Agent Circuit Breaker", version="0.1.0", lifespan=lifespan)

add_metrics_route(app)
add_rate_limiter(app, settings.rate_limit_rpm)
get_tenant = make_get_tenant(get_db)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ─── Intercept ────────────────────────────────────────────────────────────────


@app.post("/v1/intercept", response_model=InterceptResponse)
async def intercept(
    data: ToolCallIn,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    t0 = time()
    result = await intercept_tool_call(
        session=session,
        tenant_id=tenant.id,
        agent_id=data.agent_id,
        session_id=data.session_id,
        tool_name=data.tool_name,
        tool_input=data.tool_input,
        tool_output=data.tool_output,
        duration_ms=data.duration_ms,
        token_count=data.token_count,
        cost=data.cost,
        tenant_slug=tenant.slug,
    )
    verdict = result.get("decision", "allow")
    tool_calls_total.labels(verdict=verdict, tool_name=data.tool_name).inc()
    tool_duration_seconds.labels(verdict=verdict, tool_name=data.tool_name).observe(time() - t0)

    topic = TOPIC_CB_INTERCEPT.format(verdict=verdict)
    await _pub(
        make_event("circuit-breaker", topic, tenant.id, {
            "agent_id": data.agent_id,
            "tool_name": data.tool_name,
            "verdict": verdict,
            "reason": result.get("reason"),
            "risk_score": result.get("risk_score"),
            "incident_id": str(result["incident_id"]) if result.get("incident_id") else None,
        })
    )
    if result.get("incident_id"):
        await _pub(
            make_event(
                "circuit-breaker",
                TOPIC_CB_INCIDENT.format(severity="warning"),
                tenant.id,
                {
                    "agent_id": data.agent_id,
                    "incident_id": str(result["incident_id"]),
                    "tool_name": data.tool_name,
                },
            )
        )
    return result


# ─── Predict ────────────────────────────────────────────────────────────────────


@app.get("/api/v1/predict/{agent_id}")
async def predict(
    agent_id: str,
    current_tool: str | None = Query(None),
    steps: int = Query(default=5, ge=1, le=20),
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await get_prediction(session, tenant.id, agent_id, current_tool, steps)


# ─── Policies ──────────────────────────────────────────────────────────────────


@app.post("/api/v1/policies", response_model=PolicyOut, status_code=201)
async def create_policy(
    data: PolicyCreate,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Policy:
    policy = Policy(
        tenant_id=tenant.id,
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
    policies_total.labels(tenant_id=str(tenant.id)).inc()
    return policy


@app.get("/api/v1/policies", response_model=list[PolicyOut])
async def list_policies(
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> list[Policy]:
    stmt = select(Policy).where(Policy.tenant_id == tenant.id).order_by(Policy.priority.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@app.get("/api/v1/policies/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> Policy:
    stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant.id)
    result = await session.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@app.delete("/api/v1/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant.id)
    result = await session.execute(stmt)
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    await session.delete(policy)
    await session.commit()


# ─── Tool Calls ────────────────────────────────────────────────────────────────


@app.get("/api/v1/tool-calls", response_model=list[ToolCallOut])
async def list_tool_calls(
    tenant=Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, le=200),
) -> list[ToolCall]:
    stmt = select(ToolCall).where(ToolCall.tenant_id == tenant.id)
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
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> KillSwitch:
    ks = await activate_kill_switch(session, tenant.id, agent_id, reason, "manual", ttl_seconds)
    await session.commit()
    await session.refresh(ks)
    kill_switches_active.labels(agent_id=agent_id, tenant_id=str(tenant.id)).inc()
    await _pub(
        make_event("circuit-breaker", TOPIC_CB_KILL.format(action="activate"), tenant.id, {
            "agent_id": agent_id, "reason": reason, "ttl": ttl_seconds,
        })
    )
    return ks


@app.post("/api/v1/kill-switch/{agent_id}/release", response_model=KillSwitchOut)
async def release_kill(
    agent_id: str,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ks = await release_kill_switch(session, tenant.id, agent_id)
    if not ks:
        raise HTTPException(status_code=404, detail="No active kill switch for this agent")
    await session.commit()
    await session.refresh(ks)
    kill_switches_active.labels(agent_id=agent_id, tenant_id=str(tenant.id)).set(0)
    await _pub(
        make_event("circuit-breaker", TOPIC_CB_KILL.format(action="release"), tenant.id, {
            "agent_id": agent_id,
        })
    )
    return ks


@app.get("/api/v1/kill-switch/{agent_id}")
async def get_kill_status(
    agent_id: str,
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await get_kill_switch_status(session, tenant.id, agent_id)


# ─── Incidents ─────────────────────────────────────────────────────────────────


@app.get("/api/v1/incidents", response_model=list[IncidentOut])
async def list_incidents(
    tenant=Depends(get_tenant),
    agent_id: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
) -> list[Incident]:
    return await get_active_incidents(session, tenant.id, agent_id)


@app.post("/api/v1/incidents/{incident_id}/resolve")
async def resolve_incident_endpoint(
    incident_id: uuid.UUID,
    tenant=Depends(get_tenant),
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
    tenant=Depends(get_tenant),
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
    tenant=Depends(get_tenant),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    is_killed = await check_kill_switch(session, tenant.id, agent_id)

    state_stmt = (
        select(AgentState)
        .where(AgentState.tenant_id == tenant.id, AgentState.agent_id == agent_id)
        .order_by(AgentState.window_start.desc())
        .limit(1)
    )
    state_result = await session.execute(state_stmt)
    state = state_result.scalar_one_or_none()

    active_incidents = await get_active_incidents(session, tenant.id, agent_id)

    calls_stmt = (
        select(ToolCall)
        .where(ToolCall.tenant_id == tenant.id, ToolCall.agent_id == agent_id)
        .order_by(ToolCall.timestamp.desc())
        .limit(20)
    )
    calls_result = await session.execute(calls_stmt)
    recent_calls = [
        {
            "tool_name": c.tool_name,
            "decision": c.decision,
            "blocked": c.blocked,
            "timestamp": str(c.timestamp),
        }
        for c in calls_result.scalars().all()
    ]

    return {
        "agent_id": agent_id,
        "is_killed": is_killed,
        "state": state,
        "active_incidents": active_incidents,
        "recent_decisions": recent_calls,
    }
