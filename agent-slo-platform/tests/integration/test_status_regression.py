"""Regression tests for async lazy-load failures in SLO read endpoints.

`/api/v1/status` and `/api/v1/compliance/owasp` both read `slo.sli`. When the
relationship is not eager-loaded, SQLAlchemy attempts IO during attribute
access and raises `MissingGreenlet` under asyncio. The fixtures create the SLO
in the same session, so the identity map hides the bug unless we expire it
first — which is what a real request against a fresh session does.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import ServiceLevelObjective, Tenant

pytestmark = pytest.mark.asyncio


async def test_status_returns_200_with_fresh_slo_objects(
    client: AsyncClient,
    session: AsyncSession,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
    metrics_task_success: list,
) -> None:
    session.expire_all()

    resp = await client.get("/api/v1/status", headers={"X-API-Key": "acme-corp"})

    assert resp.status_code == 200
    assert [entry["slo_name"] for entry in resp.json()] == ["task-success-rate"]


async def test_owasp_report_returns_200_with_fresh_slo_objects(
    client: AsyncClient,
    session: AsyncSession,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
) -> None:
    session.expire_all()

    resp = await client.get("/api/v1/compliance/owasp", headers={"X-API-Key": "acme-corp"})

    assert resp.status_code == 200
    assert resp.json()["standard"] == "OWASP Agentic AI Top 10 2026"
