"""Integration tests for API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import Tenant


pytestmark = pytest.mark.asyncio


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_tenant(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/tenants", json={"slug": "test-tenant", "name": "Test Tenant"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "test-tenant"
    assert data["name"] == "Test Tenant"


async def test_auth_requires_api_key(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/tenants/me")
    assert resp.status_code == 422  # missing header


async def test_create_agent(
    client: AsyncClient,
    tenant: Tenant,
) -> None:
    resp = await client.post(
        "/api/v1/agents",
        json={"environment": "production", "name": "agent-1", "framework": "openai-agents"},
        headers={"X-API-Key": tenant.slug},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "agent-1"
    assert data["tenant_id"] == str(tenant.id)


async def test_create_sli(
    client: AsyncClient,
    tenant: Tenant,
) -> None:
    resp = await client.post(
        "/api/v1/slis",
        json={"name": "task_success_rate", "metric_type": "ratio", "source": "otel_attribute", "config": {}},
        headers={"X-API-Key": tenant.slug},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "task_success_rate"


async def test_create_slo(
    client: AsyncClient,
    tenant: Tenant,
    sli_task_success: ServiceLevelIndicator,
) -> None:
    resp = await client.post(
        "/api/v1/slos",
        json={
            "sli_id": str(sli_task_success.id),
            "name": "task-success",
            "target": 0.95,
            "comparator": "gt",
            "window": "7d",
        },
        headers={"X-API-Key": tenant.slug},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "task-success"
    assert data["target"] == 0.95


async def test_status_endpoint(
    client: AsyncClient,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
    metrics_task_success: list,
) -> None:
    resp = await client.get("/api/v1/status", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["slo_name"] == "task-success-rate"
    assert entry["current_value"] == pytest.approx(0.95, abs=0.01)
    assert entry["is_breaching"] is False


async def test_ingest_otlp_traces(
    client: AsyncClient,
    tenant: Tenant,
    sli_task_success: ServiceLevelIndicator,
) -> None:
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "test"}}]},
            "scopeSpans": [{
                "spans": [{
                    "traceId": "0102030405060708090a0b0c0d0e0f10",
                    "spanId": "0102030405060708",
                    "name": "agent-task",
                    "kind": 1,
                    "startTimeUnixNano": 1719300000000000000,
                    "endTimeUnixNano": 1719300001000000000,
                    "attributes": [
                        {"key": "gen_ai.eval.success", "value": {"intValue": "1"}},
                        {"key": "gen_ai.eval.total", "value": {"intValue": "1"}},
                        {"key": "agentops.agent.id", "value": {"stringValue": "agent-1"}},
                    ],
                }],
            }],
        }]
    }
    resp = await client.post("/v1/traces", json=payload, headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    data = resp.json()
    assert data["spans"] == 1
    assert data["metrics"] == 1


async def test_owasp_compliance(
    client: AsyncClient,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
) -> None:
    resp = await client.get("/api/v1/compliance/owasp", headers={"X-API-Key": tenant.slug})
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard"] == "OWASP Agentic AI Top 10 2026"
    assert len(data["controls"]) == 4
