"""Anomaly Engine — detects unusual agent behavior patterns.

Detection methods:
  1. Tool-call frequency anomaly (Z-score vs historical baseline)
  2. Behavioral drift (tool entropy shift)
  3. Reasoning-loop detection (consecutive same-tool calls)
  4. Timing anomaly (unusual duration patterns)
"""

from __future__ import annotations

import math
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import AgentState, ToolCall


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def compute_anomaly_score(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    tool_call: ToolCall,
    window_minutes: int = 5,
) -> tuple[float, dict[str, Any]]:
    scores: dict[str, float] = {}
    details: dict[str, Any] = {}

    stats = await _get_window_stats(session, tenant_id, agent_id, window_minutes)
    details["window_stats"] = stats

    freq_score = _frequency_anomaly(stats, tool_call)
    scores["frequency"] = freq_score
    details["frequency_score"] = freq_score

    entropy_score = _entropy_anomaly(stats)
    scores["entropy"] = entropy_score
    details["entropy_score"] = entropy_score

    loop_score = _reasoning_loop(stats, tool_call)
    scores["reasoning_loop"] = loop_score
    details["reasoning_loop_score"] = loop_score

    timing_score = _timing_anomaly(stats, tool_call)
    scores["timing"] = timing_score
    details["timing_score"] = timing_score

    # Weighted composite score (0-1)
    weights = {"frequency": 0.30, "entropy": 0.25, "reasoning_loop": 0.30, "timing": 0.15}
    composite = sum(weights[k] * min(scores.get(k, 0), 1.0) for k in weights)
    details["composite_score"] = composite
    details["component_scores"] = scores

    return min(composite, 1.0), details


async def _get_window_stats(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    agent_id: str,
    window_minutes: int,
) -> dict[str, Any]:
    cutoff = now_utc() - timedelta(minutes=window_minutes)

    stmt = (
        select(ToolCall)
        .where(
            ToolCall.tenant_id == tenant_id,
            ToolCall.agent_id == agent_id,
            ToolCall.timestamp >= cutoff,
        )
        .order_by(ToolCall.timestamp.desc())
    )
    result = await session.execute(stmt)
    calls = list(result.scalars().all())

    if not calls:
        return {
            "call_count": 0,
            "unique_tools": [],
            "tool_frequencies": {},
            "consecutive_same_tool": 0,
            "avg_duration_ms": 0,
            "durations": [],
            "tool_sequence": [],
            "total_tokens": 0,
        }

    durations = [c.duration_ms or 0 for c in calls]
    tool_names = [c.tool_name for c in calls]
    tool_freq = Counter(tool_names)

    # Consecutive same tool at the end of sequence
    consecutive = 0
    if len(tool_names) >= 2:
        for i in range(len(tool_names) - 1, 0, -1):
            if tool_names[i] == tool_names[i - 1]:
                consecutive += 1
            else:
                break

    return {
        "call_count": len(calls),
        "unique_tools": list(tool_freq.keys()),
        "tool_frequencies": dict(tool_freq),
        "consecutive_same_tool": consecutive,
        "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
        "durations": durations,
        "tool_sequence": tool_names,
        "total_tokens": sum(c.token_count or 0 for c in calls),
    }


def _frequency_anomaly(
    stats: dict[str, Any],
    tool_call: ToolCall,
    std_threshold: float = 2.0,
) -> float:
    tool_freq = stats.get("tool_frequencies", {})
    total = stats.get("call_count", 0)
    if total < 3:
        return 0.0

    freq_values = list(tool_freq.values())
    if len(freq_values) < 2:
        return 0.0

    mean = np.mean(freq_values)
    std = np.std(freq_values) or 1.0
    current_freq = tool_freq.get(tool_call.tool_name, 0)

    z_score = (current_freq - mean) / std
    if z_score > std_threshold:
        return min(1.0, (z_score - std_threshold) / 5.0)
    return 0.0


def _entropy_anomaly(stats: dict[str, Any]) -> float:
    tool_freq = stats.get("tool_frequencies", {})
    total = stats.get("call_count", 0)
    if total < 3 or len(tool_freq) < 2:
        return 0.0

    # Shannon entropy of tool distribution
    entropy = 0.0
    for count in tool_freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    max_entropy = math.log2(max(len(tool_freq), 2))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 1.0

    # Low entropy = highly repetitive = suspicious
    if normalized_entropy < 0.3:
        return (0.3 - normalized_entropy) / 0.3
    return 0.0


def _reasoning_loop(stats: dict[str, Any], tool_call: ToolCall) -> float:
    consecutive = stats.get("consecutive_same_tool", 0)
    threshold = 3

    if consecutive >= threshold:
        return min(1.0, (consecutive - threshold + 1) / 10.0)
    return 0.0


def _timing_anomaly(
    stats: dict[str, Any],
    tool_call: ToolCall,
    std_threshold: float = 2.5,
) -> float:
    durations = stats.get("durations", [])
    if len(durations) < 3 or tool_call.duration_ms is None:
        return 0.0

    mean = np.mean(durations)
    std = np.std(durations) or 1.0

    z_score = abs(tool_call.duration_ms - mean) / std
    if z_score > std_threshold:
        return min(1.0, (z_score - std_threshold) / 5.0)
    return 0.0


def compute_tool_entropy(tool_sequence: list[str]) -> float:
    if not tool_sequence:
        return 0.0
    freq = Counter(tool_sequence)
    if len(freq) <= 1:
        return 0.0
    total = len(tool_sequence)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    max_e = math.log2(len(freq))
    return entropy / max_e if max_e > 0 else 0.0
