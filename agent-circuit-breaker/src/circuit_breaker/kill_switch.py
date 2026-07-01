"""Kill Switch — stops an agent from making further tool calls.

Can be triggered by:
  - Policy engine (policy violation with "kill" action)
  - Anomaly engine (extreme anomaly score)
  - Risk engine (risk budget exceeded)
  - Manual (API call)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import AgentState, KillSwitch


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def check_kill_switch(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
) -> bool:
    now = now_utc()
    stmt = (
        select(KillSwitch)
        .where(
            KillSwitch.tenant_id == tenant_id,
            KillSwitch.agent_id == agent_id,
            KillSwitch.active.is_(True),
        )
        .filter((KillSwitch.expires_at.is_(None)) | (KillSwitch.expires_at > now))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def activate_kill_switch(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    reason: str,
    triggered_by: str,
    ttl_seconds: int | None = 3600,
) -> KillSwitch:
    # Deactivate any existing kill switches for this agent
    stmt = select(KillSwitch).where(
        KillSwitch.tenant_id == tenant_id,
        KillSwitch.agent_id == agent_id,
        KillSwitch.active.is_(True),
    )
    result = await session.execute(stmt)
    for ks in result.scalars().all():
        ks.active = False
        ks.released_at = now_utc()

    ks = KillSwitch(
        tenant_id=tenant_id,
        agent_id=agent_id,
        reason=reason,
        triggered_by=triggered_by,
        active=True,
        expires_at=now_utc() + timedelta(seconds=ttl_seconds) if ttl_seconds else None,
        created_at=now_utc(),
    )
    session.add(ks)

    # Also mark agent state as killed
    state_stmt = (
        select(AgentState)
        .where(
            AgentState.tenant_id == tenant_id,
            AgentState.agent_id == agent_id,
        )
        .order_by(AgentState.window_start.desc())
        .limit(1)
    )
    state_result = await session.execute(state_stmt)
    state = state_result.scalar_one_or_none()
    if state:
        state.is_killed = True

    await session.flush()
    return ks


async def release_kill_switch(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
) -> KillSwitch | None:
    stmt = select(KillSwitch).where(
        KillSwitch.tenant_id == tenant_id,
        KillSwitch.agent_id == agent_id,
        KillSwitch.active.is_(True),
    )
    result = await session.execute(stmt)
    ks = result.scalar_one_or_none()
    if ks:
        ks.active = False
        ks.released_at = now_utc()

        state_stmt = (
            select(AgentState)
            .where(
                AgentState.tenant_id == tenant_id,
                AgentState.agent_id == agent_id,
            )
            .order_by(AgentState.window_start.desc())
            .limit(1)
        )
        state_result = await session.execute(state_stmt)
        state = state_result.scalar_one_or_none()
        if state:
            state.is_killed = False

        await session.flush()
    return ks


async def get_kill_switch_status(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
) -> dict[str, Any]:
    stmt = select(KillSwitch).where(
        KillSwitch.tenant_id == tenant_id,
        KillSwitch.agent_id == agent_id,
        KillSwitch.active.is_(True),
    )
    result = await session.execute(stmt)
    ks = result.scalar_one_or_none()
    if not ks:
        return {"active": False, "agent_id": agent_id}
    return {
        "active": True,
        "agent_id": agent_id,
        "reason": ks.reason,
        "triggered_by": ks.triggered_by,
        "expires_at": ks.expires_at,
        "created_at": ks.created_at,
    }
