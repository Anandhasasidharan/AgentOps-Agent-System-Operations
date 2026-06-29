"""Risk Engine — scores the risk of each tool call before execution.

Factors:
  - Tool destructiveness (built-in weights)
  - Input sensitivity (e.g. contains destructive parameters)
  - Agent reputation (recent failure rate)
  - Cost risk (token/cost spend rate)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import ToolCall

# Built-in risk weights for known tool patterns
TOOL_RISK_WEIGHTS: dict[str, float] = {
    "delete_file": 0.95,
    "rm": 0.90,
    "write_file": 0.60,
    "execute_sql": 0.90,
    "delete_record": 0.85,
    "drop_table": 0.95,
    "execute_command": 0.95,
    "bash": 0.95,
    "subprocess": 0.90,
    "exec_python": 0.85,
    "process_payment": 0.90,
    "delete_user": 0.90,
    "create_api_key": 0.80,
    "modify_permissions": 0.85,
    "send_http_request": 0.50,
}

# Input patterns that increase risk
HIGH_RISK_INPUT_PATTERNS: list[str] = [
    "DELETE FROM",
    "DROP TABLE",
    "TRUNCATE",
    "rm -rf",
    "sudo",
    "chmod 777",
    "> /dev",
    "format(",
    "eval(",
    "exec(",
    "__import__",
    "subprocess",
    "os.system",
]


async def score_tool_call(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
    session_db: AsyncSession | None = None,
) -> tuple[float, dict[str, Any]]:
    factors: dict[str, float] = {}
    details: dict[str, Any] = {}

    base_weight = TOOL_RISK_WEIGHTS.get(tool_name, 0.20)
    factors["base_weight"] = base_weight
    details["base_weight"] = base_weight

    input_risk = _score_input_risk(tool_input)
    factors["input_risk"] = input_risk
    details["input_risk"] = input_risk

    recent_failure_rate = await _get_failure_rate(session, tenant_id, agent_id)
    factors["failure_rate"] = recent_failure_rate * 0.5
    details["failure_rate"] = recent_failure_rate

    cost_risk = await _get_cost_risk(session, tenant_id, agent_id)
    factors["cost_risk"] = cost_risk
    details["cost_risk"] = cost_risk

    weights = {"base_weight": 0.40, "input_risk": 0.30, "failure_rate": 0.15, "cost_risk": 0.15}
    composite = sum(weights[k] * factors.get(k, 0) for k in weights)
    composite = min(max(composite, 0.0), 1.0)

    details["composite_risk"] = composite
    details["factor_scores"] = factors

    return composite, details


def _score_input_risk(tool_input: dict[str, Any]) -> float:
    input_str = str(tool_input).lower()
    matches = sum(1 for p in HIGH_RISK_INPUT_PATTERNS if p.lower() in input_str)
    if matches == 0:
        return 0.0
    return min(1.0, matches * 0.30)


async def _get_failure_rate(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    window_minutes: int = 30,
) -> float:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    stmt = select(ToolCall).where(
        ToolCall.tenant_id == tenant_id,
        ToolCall.agent_id == agent_id,
        ToolCall.timestamp >= cutoff,
    )
    result = await session.execute(stmt)
    calls = list(result.scalars().all())
    if not calls:
        return 0.0
    failures = sum(1 for c in calls if c.blocked or (c.anomaly_score or 0) > 0.5)
    return failures / len(calls)


async def _get_cost_risk(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    window_minutes: int = 10,
) -> float:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    stmt = select(ToolCall).where(
        ToolCall.tenant_id == tenant_id,
        ToolCall.agent_id == agent_id,
        ToolCall.timestamp >= cutoff,
    )
    result = await session.execute(stmt)
    calls = list(result.scalars().all())
    if not calls:
        return 0.0
    total_cost = sum(float(c.cost or 0) for c in calls)
    total_tokens = sum(c.token_count or 0 for c in calls)
    # Normalize: $1/min or 100K tokens/min = high risk
    cost_rate = total_cost / (window_minutes / 60) if window_minutes > 0 else 0
    token_rate = total_tokens / window_minutes if window_minutes > 0 else 0
    cost_factor = min(1.0, cost_rate / 1.0)
    token_factor = min(1.0, token_rate / 100000)
    return max(cost_factor, token_factor)
