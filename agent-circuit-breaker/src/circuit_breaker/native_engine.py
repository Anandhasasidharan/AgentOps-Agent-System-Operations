"""Engine selection for Circuit Breaker intercept policy evaluation."""

from __future__ import annotations

import os
from typing import Any

from circuit_breaker.policy_engine import PolicyDecision, evaluate_policies, load_policies

try:  # The native engine is optional until M5; the Python engine is the default.
    from agentops_engine import AoCall, CEngine, compile_policy_models
except Exception:  # pragma: no cover - exercised only when the engine is absent
    AoCall = None
    CEngine = None
    compile_policy_models = None


def get_engine_name() -> str:
    return os.environ.get("AGENTOPS_ENGINE", "py").lower()


async def evaluate_policies_selected(
    session: Any,
    tenant_id: Any,
    tool_call: Any,
    policies: list[Any] | None = None,
    windowed_stats: dict[str, Any] | None = None,
) -> PolicyDecision:
    name = get_engine_name()
    if name == "py":
        return await evaluate_policies(session, tenant_id, tool_call, policies, windowed_stats)
    if name == "auto":
        try:
            return await _evaluate_with_c(session, tenant_id, tool_call, policies, windowed_stats)
        except Exception:
            return await evaluate_policies(session, tenant_id, tool_call, policies, windowed_stats)
    if name == "c":
        return await _evaluate_with_c(session, tenant_id, tool_call, policies, windowed_stats)
    raise RuntimeError(f"Unknown AGENTOPS_ENGINE: {name}")


async def _evaluate_with_c(
    session: Any,
    tenant_id: Any,
    tool_call: Any,
    policies: list[Any] | None = None,
    windowed_stats: dict[str, Any] | None = None,
) -> PolicyDecision:
    if CEngine is None or compile_policy_models is None or AoCall is None:
        raise RuntimeError(
            "agentops-engine is not installed or failed to build; "
            "install agentops-engine or set AGENTOPS_ENGINE=py"
        )
    if policies is None:
        policies = await load_policies(session, tenant_id)
    blob = compile_policy_models(policies)
    engine = CEngine()
    engine.load_policy(blob)
    now_ns = (
        int(tool_call.timestamp.timestamp() * 1_000_000_000)
        if getattr(tool_call, "timestamp", None)
        else 0
    )
    call = AoCall(
        agent_id=tool_call.agent_id,
        tool=tool_call.tool_name,
        input=str(tool_call.tool_input),
        tokens=tool_call.token_count or 0,
        cost_micro=int(float(tool_call.cost or 0) * 1_000_000),
        now_ns=now_ns,
        minute_of_day=(now_ns // 60_000_000_000) % (24 * 60),
        weekday=(now_ns // 86_400_000_000_000) % 7,
        risk_score_micro=int(float(tool_call.risk_score or 0) * 1_000_000),
        anomaly_score_micro=int(float(tool_call.anomaly_score or 0) * 1_000_000),
    )
    result = engine.intercept(call)
    engine.close()
    if result.verdict == 0:
        return PolicyDecision(allowed=True, action="allow")
    return PolicyDecision(
        allowed=False,
        action="block",
        reason=f"native-engine-reason-{result.reason_code}",
        policy_name=f"compiled-{result.policy_index}",
    )
