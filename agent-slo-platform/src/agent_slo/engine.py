"""SLO evaluation, error budget, and burn-rate engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import ErrorBudget, Metric, ServiceLevelIndicator, ServiceLevelObjective
from agent_slo.yaml_spec import window_to_seconds


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def evaluate_slo(value: float, target: float, comparator: str) -> bool:
    if comparator == "gt":
        return value >= target
    if comparator == "lt":
        return value <= target
    return abs(value - target) < 1e-9


def compute_burn_rate(consumed: float, window_seconds: int, elapsed_seconds: float) -> float:
    if window_seconds <= 0 or elapsed_seconds <= 0:
        return 0.0
    elapsed_fraction = elapsed_seconds / window_seconds
    return consumed / elapsed_fraction if elapsed_fraction > 0 else 0.0


def window_bounds(window: str, anchor: datetime | None = None) -> tuple[datetime, datetime]:
    end = anchor or now_utc()
    seconds = window_to_seconds(window)
    start = end - timedelta(seconds=seconds)
    return start, end


async def aggregate_sli(
    session: AsyncSession,
    sli: ServiceLevelIndicator,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    window: str,
    anchor: datetime | None = None,
) -> tuple[float, int]:
    start, end = window_bounds(window, anchor)
    stmt = select(Metric).where(
        Metric.tenant_id == tenant_id,
        Metric.sli_id == sli.id,
        Metric.timestamp >= start,
        Metric.timestamp <= end,
    )
    if agent_id:
        stmt = stmt.where(Metric.agent_id == agent_id)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    sli_name = sli.name
    if sli_name in {"task_success_rate", "hallucination_rate", "tool_accuracy"}:
        total = sum(m.count for m in rows)
        if total == 0:
            return 0.0, 0
        weighted = sum(m.value * m.count for m in rows)
        return weighted / total, total
    if sli_name in {"cost_per_task", "steps_to_completion", "latency_p99", "token_usage"}:
        if not rows:
            return 0.0, 0
        values = [m.value for m in rows]
        if sli_name == "latency_p99":
            sorted_vals = sorted(values)
            idx = int(len(sorted_vals) * 0.99)
            return sorted_vals[min(idx, len(sorted_vals) - 1)], len(values)
        return sum(values) / len(values), len(values)

    # default: average
    if not rows:
        return 0.0, 0
    total_count = sum(m.count for m in rows)
    weighted = sum(m.value * m.count for m in rows)
    return weighted / total_count, total_count


async def get_or_create_error_budget(
    session: AsyncSession,
    slo: ServiceLevelObjective,
    period_start: datetime,
) -> ErrorBudget:
    stmt = select(ErrorBudget).where(
        ErrorBudget.slo_id == slo.id,
        ErrorBudget.period_start == period_start,
    )
    result = await session.execute(stmt)
    budget = result.scalar_one_or_none()
    if budget:
        return budget

    window_seconds = window_to_seconds(slo.window)
    period_end = period_start + timedelta(seconds=window_seconds)
    total_budget = 1.0 - slo.target if slo.comparator == "gt" else slo.target
    budget = ErrorBudget(
        slo_id=slo.id,
        period_start=period_start,
        period_end=period_end,
        total_budget=total_budget,
        consumed=0.0,
        remaining=total_budget,
    )
    session.add(budget)
    await session.flush()
    return budget


async def evaluate_all_slos(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    anchor: datetime | None = None,
) -> list[dict[str, Any]]:
    stmt = select(ServiceLevelObjective).where(
        ServiceLevelObjective.tenant_id == tenant_id,
    )
    result = await session.execute(stmt)
    slos = result.scalars().all()

    statuses: list[dict[str, Any]] = []
    for slo in slos:
        start, end = window_bounds(slo.window, anchor)
        value, count = await aggregate_sli(
            session,
            slo.sli,
            tenant_id,
            slo.agent_id,
            slo.window,
            anchor,
        )
        is_breaching = not evaluate_slo(value, slo.target, slo.comparator)

        # budget math
        if slo.comparator == "gt":
            consumed = max(0.0, slo.target - value)
        elif slo.comparator == "lt":
            consumed = max(0.0, value - slo.target)
        else:
            consumed = abs(value - slo.target)

        budget = await get_or_create_error_budget(session, slo, start)
        budget.consumed = min(consumed, budget.total_budget)
        budget.remaining = budget.total_budget - budget.consumed

        elapsed_seconds = ((anchor or now_utc()) - start).total_seconds()
        burn_rate = compute_burn_rate(
            budget.consumed, window_to_seconds(slo.window), elapsed_seconds
        )

        statuses.append(
            {
                "slo_id": slo.id,
                "slo_name": slo.name,
                "sli_name": slo.sli.name,
                "window": slo.window,
                "target": slo.target,
                "current_value": value,
                "comparator": slo.comparator,
                "is_breaching": is_breaching,
                "budget_consumed": budget.consumed,
                "budget_remaining": budget.remaining,
                "burn_rate": burn_rate,
                "sample_count": count,
                "alert_thresholds": slo.burn_rate_alert_thresholds or [],
            }
        )

    await session.commit()
    return statuses
