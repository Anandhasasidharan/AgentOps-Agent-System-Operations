"""Alert evaluation and dispatch."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import Alert, ServiceLevelObjective


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def evaluate_alerts(
    session: AsyncSession,
    slo: ServiceLevelObjective,
    burn_rate: float,
) -> list[Alert]:
    """Create new alerts if burn_rate crosses thresholds."""
    fired: list[Alert] = []
    # find existing unresolved alerts to avoid duplicates at same threshold
    stmt = select(Alert).where(
        Alert.slo_id == slo.id,
        Alert.resolved_at.is_(None),
    )
    result = await session.execute(stmt)
    unresolved = {(a.severity, a.threshold) for a in result.scalars().all()}

    for spec in slo.burn_rate_alert_thresholds:
        if (
            burn_rate >= spec["threshold"]
            and (spec["severity"], spec["threshold"]) not in unresolved
        ):
            alert = Alert(
                tenant_id=slo.tenant_id,
                slo_id=slo.id,
                severity=spec["severity"],
                threshold=spec["threshold"],
                burn_rate=burn_rate,
                message=(
                    f"SLO '{slo.name}' burn rate {burn_rate:.2%} exceeded "
                    f"{spec['severity']} threshold {spec['threshold']:.2%}"
                ),
                fired_at=now_utc(),
            )
            session.add(alert)
            fired.append(alert)

    if fired:
        await session.flush()
    return fired


async def resolve_alerts(
    session: AsyncSession,
    slo_id: uuid.UUID,
    burn_rate: float,
    thresholds: list[dict[str, Any]],
) -> list[Alert]:
    """Resolve alerts whose thresholds are no longer crossed."""
    active_thresholds = {t["threshold"] for t in thresholds if burn_rate >= t["threshold"]}
    stmt = select(Alert).where(
        Alert.slo_id == slo_id,
        Alert.resolved_at.is_(None),
        Alert.threshold.notin_(active_thresholds) if active_thresholds else True,
    )
    result = await session.execute(stmt)
    resolved: list[Alert] = []
    for alert in result.scalars().all():
        alert.resolved_at = now_utc()
        resolved.append(alert)
    if resolved:
        await session.flush()
    return resolved
