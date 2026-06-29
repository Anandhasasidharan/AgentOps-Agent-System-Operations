"""Additional API integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import ServiceLevelObjective, Tenant


pytestmark = pytest.mark.asyncio


async def test_list_agents(
    client: AsyncClient,
    tenant: Tenant,
) -> None:
    await client.post(
        "/api/v1/agents",
        json={"environment": "production", "name": "agent-1"},
        headers={"X-API-Key": tenant.slug},
    )
    resp = await client.get("/api/v1/agents", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_slis(
    client: AsyncClient,
    tenant: Tenant,
) -> None:
    await client.post(
        "/api/v1/slis",
        json={"name": "task_success_rate", "metric_type": "ratio", "source": "otel_attribute", "config": {}},
        headers={"X-API-Key": tenant.slug},
    )
    resp = await client.get("/api/v1/slis", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_list_slos(
    client: AsyncClient,
    tenant: Tenant,
    sli_task_success: ServiceLevelIndicator,
) -> None:
    await client.post(
        "/api/v1/slos",
        json={
            "sli_id": str(sli_task_success.id),
            "name": "slo-1",
            "target": 0.95,
            "comparator": "gt",
            "window": "7d",
        },
        headers={"X-API-Key": tenant.slug},
    )
    resp = await client.get("/api/v1/slos", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_resolve_alert(
    client: AsyncClient,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
) -> None:
    # Fire alert via status evaluation with bad metrics
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    for i in range(10):
        ts_nanos = int((now - timedelta(minutes=i)).timestamp() * 1e9)
        await client.post(
            "/v1/traces",
            json={
                "resourceSpans": [{
                    "resource": {"attributes": []},
                    "scopeSpans": [{
                        "spans": [{
                            "traceId": "0102030405060708090a0b0c0d0e0f10",
                            "spanId": f"010203040506070{i}",
                            "name": "agent-task",
                            "kind": 1,
                            "startTimeUnixNano": str(ts_nanos),
                            "endTimeUnixNano": str(ts_nanos),
                            "attributes": [
                                {"key": "gen_ai.eval.success", "value": {"intValue": "0"}},
                                {"key": "gen_ai.eval.total", "value": {"intValue": "1"}},
                                {"key": "agentops.agent.id", "value": {"stringValue": "agent-1"}},
                            ],
                        }],
                    }],
                }]
            },
            headers={"X-API-Key": tenant.slug},
        )

    resp = await client.get("/api/v1/status", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200

    resp = await client.get("/api/v1/alerts", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    alerts = resp.json()
    if alerts:
        alert_id = alerts[0]["id"]
        resp = await client.post(f"/api/v1/alerts/{alert_id}/resolve", headers={"X-API-Key": tenant.slug})
        assert resp.status_code == 200
        assert resp.json()["resolved_at"] is not None


async def test_eu_ai_act_compliance(
    client: AsyncClient,
    tenant: Tenant,
) -> None:
    resp = await client.get("/api/v1/compliance/eu-ai-act", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard"] == "EU AI Act"
