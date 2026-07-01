"""Compliance report generators."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_slo.models import ServiceLevelObjective

OWASP_AGENTIC_CONTROLS: list[dict[str, Any]] = [
    {
        "risk_id": "ASI07",
        "risk_name": "Uncontrolled Costs",
        "required_sli_kinds": ["cost_per_task", "token_usage"],
    },
    {
        "risk_id": "ASI08",
        "risk_name": "Cascading Agent Failures",
        "required_sli_kinds": ["latency_p99", "task_success_rate"],
    },
    {
        "risk_id": "ASI09",
        "risk_name": "Lack of Observability",
        "required_sli_kinds": ["task_success_rate", "tool_accuracy"],
    },
    {
        "risk_id": "ASI10",
        "risk_name": "Inadequate Testing",
        "required_sli_kinds": ["hallucination_rate", "tool_accuracy"],
    },
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def generate_owasp_report(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    stmt = select(ServiceLevelObjective).where(ServiceLevelObjective.tenant_id == tenant_id)
    result = await session.execute(stmt)
    slos = result.scalars().all()
    configured_sli_kinds = {slo.sli.name for slo in slos}

    controls = []
    for control in OWASP_AGENTIC_CONTROLS:
        covered = [k for k in control["required_sli_kinds"] if k in configured_sli_kinds]
        gaps = [k for k in control["required_sli_kinds"] if k not in configured_sli_kinds]
        if covered and not gaps:
            status = "mitigated"
        elif covered:
            status = "partially_mitigated"
        else:
            status = "not_mitigated"

        controls.append(
            {
                "risk_id": control["risk_id"],
                "risk_name": control["risk_name"],
                "status": status,
                "evidence": [f"SLO configured for {k}" for k in covered],
                "gaps": [f"No SLO configured for {k}" for k in gaps],
            }
        )

    return {
        "generated_at": now_utc(),
        "standard": "OWASP Agentic AI Top 10 2026",
        "tenant": str(tenant_id),
        "controls": controls,
    }
