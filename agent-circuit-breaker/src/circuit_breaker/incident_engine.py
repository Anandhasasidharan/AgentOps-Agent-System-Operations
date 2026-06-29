"""Incident Engine — creates and manages incidents from circuit breaker events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import Incident


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def create_incident(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    session_id: str | None,
    severity: str,
    category: str,
    message: str,
    details: dict[str, Any],
    action_taken: str,
    tool_call_id: uuid.UUID | None = None,
) -> Incident:
    incident = Incident(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        severity=severity,
        category=category,
        message=message,
        details=details,
        action_taken=action_taken,
        tool_call_id=tool_call_id,
        created_at=now_utc(),
    )
    session.add(incident)
    await session.flush()
    return incident


async def resolve_incident(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> Incident | None:
    stmt = select(Incident).where(Incident.id == incident_id)
    result = await session.execute(stmt)
    incident = result.scalar_one_or_none()
    if incident:
        incident.resolved_at = now_utc()
        await session.flush()
    return incident


async def get_active_incidents(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str | None = None,
) -> list[Incident]:
    from sqlalchemy import and_

    conditions = [Incident.tenant_id == tenant_id, Incident.resolved_at.is_(None)]
    if agent_id:
        conditions.append(Incident.agent_id == agent_id)

    stmt = select(Incident).where(and_(*conditions)).order_by(Incident.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
