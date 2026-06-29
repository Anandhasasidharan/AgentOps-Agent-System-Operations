"""Tests for OTel receiver."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import Agent, Metric, OtelSpan, ServiceLevelIndicator, Tenant
from agent_slo.receiver import ingest_traces


pytestmark = pytest.mark.asyncio


SAMPLE_OTLP = {
    "resourceSpans": [{
        "resource": {"attributes": []},
        "scopeSpans": [{
            "spans": [{
                "traceId": "0102030405060708090a0b0c0d0e0f10",
                "spanId": "0102030405060708",
                "name": "agent-task",
                "kind": 1,
                "startTimeUnixNano": "1719300000000000000",
                "endTimeUnixNano": "1719300001000000000",
                "attributes": [
                    {"key": "gen_ai.eval.success", "value": {"intValue": "1"}},
                    {"key": "gen_ai.eval.total", "value": {"intValue": "1"}},
                    {"key": "agentops.agent.id", "value": {"stringValue": "agent-1"}},
                    {"key": "agentops.environment", "value": {"stringValue": "production"}},
                ],
            }],
        }],
    }]
}


async def test_ingest_traces_creates_agent_and_metric(
    session: AsyncSession,
    tenant: Tenant,
    sli_task_success: ServiceLevelIndicator,
) -> None:
    counts = await ingest_traces(session, SAMPLE_OTLP, tenant.id)
    await session.commit()

    assert counts["spans"] == 1
    assert counts["metrics"] == 1

    stmt = select(Agent).where(Agent.tenant_id == tenant.id)
    result = await session.execute(stmt)
    agents = result.scalars().all()
    assert len(agents) == 1
    assert agents[0].name == "agent-1"

    stmt = select(Metric).where(Metric.tenant_id == tenant.id)
    result = await session.execute(stmt)
    metrics = result.scalars().all()
    assert len(metrics) == 1
    assert metrics[0].value == 1.0

    stmt = select(OtelSpan).where(OtelSpan.tenant_id == tenant.id)
    result = await session.execute(stmt)
    spans = result.scalars().all()
    assert len(spans) == 1
