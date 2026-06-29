"""Tests for compliance report generator."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.compliance import generate_owasp_report
from agent_slo.models import ServiceLevelObjective, Tenant


pytestmark = pytest.mark.asyncio


async def test_generate_owasp_report_mitigated(
    session: AsyncSession,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
) -> None:
    report = await generate_owasp_report(session, tenant.id)
    assert report["standard"] == "OWASP Agentic AI Top 10 2026"
    assert report["tenant"] == str(tenant.id)
    # task_success_rate mitigates ASI09 and partially ASI08
    asi09 = next(c for c in report["controls"] if c["risk_id"] == "ASI09")
    assert asi09["status"] in ("mitigated", "partially_mitigated")


async def test_generate_owasp_report_not_mitigated(
    session: AsyncSession,
    tenant: Tenant,
) -> None:
    report = await generate_owasp_report(session, tenant.id)
    statuses = {c["status"] for c in report["controls"]}
    assert "not_mitigated" in statuses
