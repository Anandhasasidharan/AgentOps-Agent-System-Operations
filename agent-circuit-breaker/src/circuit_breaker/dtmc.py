from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import ToolCall

STATE_BLOCKED = "__BLOCKED__"
STATE_ERROR = "__ERROR__"

STATE_CATEGORIES: dict[str, str] = {
    "delete": "destructive",
    "rm": "destructive",
    "write": "destructive",
    "drop": "destructive",
    "execute": "execution",
    "bash": "execution",
    "subprocess": "execution",
    "exec_python": "execution",
    "eval": "execution",
    "sql": "data",
    "db": "data",
    "read": "data",
    "query": "data",
    "select": "data",
    "user": "identity",
    "permission": "identity",
    "auth": "identity",
    "key": "identity",
    "payment": "finance",
    "cost": "finance",
    "price": "finance",
}

MAX_STATES = 100


def _collapse_tool(tool_name: str) -> str:
    low = tool_name.lower()
    for prefix, category in STATE_CATEGORIES.items():
        if low.startswith(prefix):
            return category
    return "other"


async def build_dtmc(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    window_minutes: int = 60,
    collapse: bool = True,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    stmt = (
        select(ToolCall)
        .where(
            ToolCall.tenant_id == tenant_id,
            ToolCall.agent_id == agent_id,
            ToolCall.timestamp >= cutoff,
        )
        .order_by(ToolCall.timestamp.asc())
    )
    result = await session.execute(stmt)
    calls = list(result.scalars().all())
    if len(calls) < 3:
        return {
            "states": [], "matrix": None, "transitions": len(calls),
            "error": "insufficient_data",
        }

    sessions: dict[str, list[ToolCall]] = defaultdict(list)
    for c in calls:
        sid = c.session_id or "default"
        sessions[sid].append(c)

    raw_states: set[str] = set()
    for c in calls:
        raw_states.add(_collapse_tool(c.tool_name) if collapse else c.tool_name)

    if len(raw_states) > MAX_STATES and collapse:
        raw_states = set(STATE_CATEGORIES.values()) | {"other"}

    state_list = sorted(raw_states)
    state_to_idx = {s: i for i, s in enumerate(state_list)}
    blocked_idx = len(state_list)
    error_idx = len(state_list) + 1
    n = len(state_list) + 2

    transition_counts: dict[tuple[int, int], int] = defaultdict(int)

    for sid, seq in sessions.items():
        for i in range(len(seq)):
            cur_call = seq[i]
            cur_state = _collapse_tool(cur_call.tool_name) if collapse else cur_call.tool_name
            if cur_state not in state_to_idx:
                continue
            cur_idx = state_to_idx[cur_state]

            if cur_call.blocked:
                transition_counts[(cur_idx, blocked_idx)] += 1
                continue

            if i + 1 < len(seq):
                next_call = seq[i + 1]
                next_state = _collapse_tool(next_call.tool_name) if collapse else next_call.tool_name  # noqa: E501
                if next_state not in state_to_idx:
                    continue
                next_idx = state_to_idx[next_state]
                transition_counts[(cur_idx, next_idx)] += 1
            else:
                transition_counts[(cur_idx, blocked_idx if cur_call.blocked else error_idx)] += 1

    for idx in range(n):
        has_outgoing = any(transition_counts.get((idx, j), 0) > 0 for j in range(n))
        if not has_outgoing:
            transition_counts[(idx, idx)] += 1

    matrix = np.zeros((n, n), dtype=np.float64)
    for (i, j), count in transition_counts.items():
        matrix[i, j] = count
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    matrix = matrix / row_sums

    total_transitions = sum(transition_counts.values())

    return {
        "states": state_list,
        "blocked_idx": int(blocked_idx),
        "error_idx": int(error_idx),
        "matrix": matrix,
        "transitions": total_transitions,
        "n": int(n),
    }


def predict_risk(
    dtmc: dict[str, Any],
    current_tool: str,
    steps: int = 5,
    delta: float = 0.05,
    collapse: bool = True,
) -> dict[str, float]:
    if dtmc.get("matrix") is None:
        return {"probability": 0.0, "eps": 0.0, "ci_low": 0.0, "ci_high": 0.0}

    matrix = dtmc["matrix"]
    state_list = dtmc["states"]
    blocked_idx = dtmc["blocked_idx"]
    n = dtmc["n"]

    cur_state = _collapse_tool(current_tool) if collapse else current_tool
    if cur_state not in state_list:
        return {"probability": 0.0, "eps": 0.0, "ci_low": 0.0, "ci_high": 0.0}

    pi = np.zeros(n, dtype=np.float64)
    pi[state_list.index(cur_state)] = 1.0

    p_power = np.eye(n, dtype=np.float64)
    for _ in range(steps):
        p_power = p_power @ matrix

    prob = float(pi @ p_power[:, blocked_idx])

    total = dtmc["transitions"]
    eps = math.sqrt(math.log(2.0 / delta) / (2.0 * total)) if total > 0 else 1.0
    ci_low = max(0.0, prob - eps)
    ci_high = min(1.0, prob + eps)

    return {
        "probability": round(prob, 4),
        "eps": round(eps, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
    }
