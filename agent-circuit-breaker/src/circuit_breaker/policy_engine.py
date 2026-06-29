"""Policy Engine — evaluates tool calls against defined policies."""

from __future__ import annotations

import fnmatch
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from circuit_breaker.models import Policy, ToolCall


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PolicyDecision:
    def __init__(
        self,
        allowed: bool,
        action: str,
        policy_id: uuid.UUID | None = None,
        policy_name: str | None = None,
        reason: str | None = None,
    ):
        self.allowed = allowed
        self.action = action
        self.policy_id = policy_id
        self.policy_name = policy_name
        self.reason = reason


async def load_policies(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[Policy]:
    stmt = (
        select(Policy)
        .where(Policy.tenant_id == tenant_id, Policy.enabled.is_(True))
        .order_by(Policy.priority.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def evaluate_policies(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    tool_call: ToolCall,
    policies: list[Policy] | None = None,
    windowed_stats: dict[str, Any] | None = None,
) -> PolicyDecision:
    if policies is None:
        policies = await load_policies(session, tenant_id)

    for policy in policies:
        if _matches_policy(policy, tool_call, windowed_stats):
            if policy.action == "allow":
                return PolicyDecision(
                    allowed=True,
                    action="allow",
                    policy_id=policy.id,
                    policy_name=policy.name,
                )
            return PolicyDecision(
                allowed=False,
                action=policy.action,
                policy_id=policy.id,
                policy_name=policy.name,
                reason=_build_reason(policy, tool_call),
            )

    return PolicyDecision(allowed=True, action="allow")


def _matches_policy(
    policy: Policy,
    tool_call: ToolCall,
    windowed_stats: dict[str, Any] | None = None,
) -> bool:
    cond = policy.conditions
    tool_name = tool_call.tool_name

    if policy.policy_type == "tool_allowlist":
        allowed = cond.get("tools", [])
        for pattern in allowed:
            if fnmatch.fnmatch(tool_name, pattern):
                return False
        return tool_name not in allowed

    if policy.policy_type == "tool_blocklist":
        blocked = cond.get("tools", [])
        for pattern in blocked:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

    if policy.policy_type == "rate_limit":
        if windowed_stats is None:
            return False
        max_calls = cond.get("max_calls", 0)
        if max_calls > 0 and windowed_stats.get("call_count", 0) >= max_calls:
            return True

    if policy.policy_type == "token_budget":
        if windowed_stats is None:
            return False
        max_tokens = cond.get("max_tokens", 0)
        if max_tokens > 0 and windowed_stats.get("total_tokens", 0) >= max_tokens:
            return True

    if policy.policy_type == "risk_threshold":
        max_risk = cond.get("max_risk_score", 1.0)
        if tool_call.risk_score is not None and tool_call.risk_score > max_risk:
            return True

    if policy.policy_type == "anomaly_threshold":
        max_anomaly = cond.get("max_anomaly_score", 1.0)
        if tool_call.anomaly_score is not None and tool_call.anomaly_score > max_anomaly:
            return True

    if policy.policy_type == "time_window":
        start = cond.get("start")
        end = cond.get("end")
        if start and end:
            now = now_utc()
            current_hour = now.hour + now.minute / 60
            if start <= current_hour <= end:
                return True

    if policy.policy_type == "reasoning_loop":
        if windowed_stats is None:
            return False
        max_same_tool = cond.get("max_consecutive_same_tool", 5)
        consecutive = windowed_stats.get("consecutive_same_tool", 0)
        if consecutive >= max_same_tool:
            return True

    return False


def _build_reason(policy: Policy, tool_call: ToolCall) -> str:
    cond = policy.conditions
    base = f"Policy '{policy.name}' ({policy.policy_type}) blocked tool '{tool_call.tool_name}'"

    if policy.policy_type == "tool_blocklist":
        return f"{base}: tool is in blocklist"
    if policy.policy_type == "tool_allowlist":
        return f"{base}: tool is not in allowlist"
    if policy.policy_type == "rate_limit":
        return f"{base}: rate limit of {cond.get('max_calls', '?')} calls exceeded"
    if policy.policy_type == "token_budget":
        return f"{base}: token budget of {cond.get('max_tokens', '?')} exceeded"
    if policy.policy_type == "risk_threshold":
        return f"{base}: risk score {tool_call.risk_score:.2f} exceeds threshold {cond.get('max_risk_score', '?')}"
    if policy.policy_type == "anomaly_threshold":
        return f"{base}: anomaly score {tool_call.anomaly_score:.2f} exceeds threshold"
    if policy.policy_type == "reasoning_loop":
        return f"{base}: possible reasoning loop detected"
    return base
