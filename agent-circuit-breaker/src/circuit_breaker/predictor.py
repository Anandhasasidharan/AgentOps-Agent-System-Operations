from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.dtmc import build_dtmc, predict_risk


async def get_prediction(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    current_tool: str | None = None,
    steps: int = 5,
) -> dict[str, Any]:
    dtmc = await build_dtmc(session, tenant_id, agent_id)
    if dtmc.get("matrix") is None:
        return {
            "probability": 0.0,
            "eps": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "available": False,
            "transitions": dtmc.get("transitions", 0),
            "states": [],
        }

    pred = predict_risk(dtmc, current_tool or "", steps=steps)
    pred["available"] = True
    pred["transitions"] = dtmc["transitions"]
    pred["states"] = dtmc["states"]
    return pred


async def compute_proactive_risk(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    current_tool: str,
) -> float:
    pred = await get_prediction(session, tenant_id, agent_id, current_tool)
    if not pred.get("available"):
        return 0.0
    prob = pred["probability"]
    ci_high = pred["ci_high"]
    return max(prob, ci_high * 0.5)
