"""Advanced engine tests with real DB state."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.engine import aggregate_sli, evaluate_all_slos, window_bounds
from agent_slo.models import (
    Agent,
    Metric,
    ServiceLevelIndicator,
    ServiceLevelObjective,
    Tenant,
)
from agent_slo.yaml_spec import window_to_seconds


pytestmark = pytest.mark.asyncio


async def test_evaluate_all_slos_with_metrics(
    session: AsyncSession,
    tenant: Tenant,
    agent: Agent,
    sli_task_success: ServiceLevelIndicator,
    slo_task_success: ServiceLevelObjective,
    metrics_task_success: list[Metric],
) -> None:
    statuses = await evaluate_all_slos(session, tenant.id)
    assert len(statuses) == 1
    status = statuses[0]
    assert status["slo_name"] == "task-success-rate"
    assert status["current_value"] == pytest.approx(0.95, abs=0.01)
    assert status["is_breaching"] is False
    assert status["budget_consumed"] == pytest.approx(0.0, abs=0.01)
    assert status["sample_count"] == 100


async def test_evaluate_all_slos_breach(
    session: AsyncSession,
    tenant: Tenant,
    agent: Agent,
    sli_task_success: ServiceLevelIndicator,
    slo_task_success: ServiceLevelObjective,
) -> None:
    from datetime import datetime, timedelta, timezone
    # Insert all-failing metrics
    now = datetime.now(timezone.utc)
    metrics = []
    for i in range(10):
        metrics.append(Metric(
            tenant_id=tenant.id,
            agent_id=agent.id,
            sli_id=sli_task_success.id,
            timestamp=now - timedelta(minutes=i),
            value=0.0,
            count=1,
            window_start=now - timedelta(minutes=i + 1),
            window_end=now - timedelta(minutes=i),
        ))
    session.add_all(metrics)
    await session.commit()

    statuses = await evaluate_all_slos(session, tenant.id)
    assert statuses[0]["is_breaching"] is True
    # total_budget = 1 - target = 0.05; consumed = min(0.95, 0.05) = 0.05
    assert statuses[0]["budget_consumed"] == pytest.approx(0.05, abs=0.01)


async def test_aggregate_sli_threshold_type(
    session: AsyncSession,
    tenant: Tenant,
    agent: Agent,
) -> None:
    from datetime import datetime, timedelta, timezone
    sli = ServiceLevelIndicator(
        tenant_id=tenant.id,
        name="latency_p99",
        metric_type="threshold",
        source="otel_attribute",
        config={},
    )
    session.add(sli)
    await session.commit()
    await session.refresh(sli)

    now = datetime.now(timezone.utc)
    for i in range(100):
        session.add(Metric(
            tenant_id=tenant.id,
            agent_id=agent.id,
            sli_id=sli.id,
            timestamp=now - timedelta(minutes=i),
            value=float(i),
            count=1,
            window_start=now - timedelta(minutes=i + 1),
            window_end=now - timedelta(minutes=i),
        ))
    await session.commit()

    value, count = await aggregate_sli(session, sli, tenant.id, agent.id, "7d")
    assert value == 99.0  # p99 of 0..99
    assert count == 100
