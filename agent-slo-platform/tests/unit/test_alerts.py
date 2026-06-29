"""Tests for alert engine."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.alerts import evaluate_alerts, resolve_alerts
from agent_slo.models import Alert, ServiceLevelObjective, Tenant


pytestmark = pytest.mark.asyncio


async def test_evaluate_alerts_creates_alert(
    session: AsyncSession,
    tenant: Tenant,
    slo_task_success: ServiceLevelObjective,
) -> None:
    fired = await evaluate_alerts(session, slo_task_success, 0.15)
    assert len(fired) == 2
    assert fired[0].severity == "info"
    assert fired[1].severity == "critical"

    stmt = select(Alert).where(Alert.tenant_id == tenant.id)
    result = await session.execute(stmt)
    assert result.scalars().all()


async def test_evaluate_alerts_does_not_duplicate(
    session: AsyncSession,
    slo_task_success: ServiceLevelObjective,
) -> None:
    await evaluate_alerts(session, slo_task_success, 0.15)
    await evaluate_alerts(session, slo_task_success, 0.16)
    stmt = select(Alert).where(Alert.slo_id == slo_task_success.id)
    result = await session.execute(stmt)
    assert len(result.scalars().all()) == 2


async def test_resolve_alerts(
    session: AsyncSession,
    slo_task_success: ServiceLevelObjective,
) -> None:
    await evaluate_alerts(session, slo_task_success, 0.15)
    resolved = await resolve_alerts(
        session,
        slo_task_success.id,
        0.01,
        slo_task_success.burn_rate_alert_thresholds,
    )
    assert len(resolved) == 2
    for alert in resolved:
        assert alert.resolved_at is not None
