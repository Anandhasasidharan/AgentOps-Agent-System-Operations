"""SLO breach events must identify the agent so enforcement can act on it."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agentops_core.base import Tenant
from agent_slo.models import Agent, Metric, ServiceLevelIndicator, ServiceLevelObjective


@pytest.mark.asyncio
async def test_breach_event_includes_agent_id(
    client: AsyncClient,
    session: AsyncSession,
    tenant: Tenant,
    agent: Agent,
    sli_task_success: ServiceLevelIndicator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slo = ServiceLevelObjective(
        tenant_id=tenant.id,
        agent_id=agent.id,
        sli_id=sli_task_success.id,
        name="agent-scoped-success",
        target=0.95,
        comparator="gt",
        window="7d",
    )
    session.add(slo)

    now = datetime.now(timezone.utc)
    for i in range(10):
        session.add(
            Metric(
                tenant_id=tenant.id,
                agent_id=agent.id,
                sli_id=sli_task_success.id,
                timestamp=now - timedelta(minutes=i),
                value=1.0 if i < 5 else 0.0,
                count=1,
                window_start=now - timedelta(minutes=i + 1),
                window_end=now - timedelta(minutes=i),
            )
        )
    await session.commit()

    events: list = []

    async def capture(event) -> None:
        events.append(event)

    monkeypatch.setattr("agent_slo.api._pub", capture)

    resp = await client.get("/api/v1/status", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200, resp.text

    breaches = [e for e in events if e.event_type.startswith("agentops.slo.breach.")]
    assert len(breaches) == 1
    assert breaches[0].payload["agent_id"] == str(agent.id)
    assert breaches[0].tenant_id == tenant.id

    # Guard against a regression where a different UUID is serialized.
    assert uuid.UUID(breaches[0].payload["agent_id"]) == agent.id
