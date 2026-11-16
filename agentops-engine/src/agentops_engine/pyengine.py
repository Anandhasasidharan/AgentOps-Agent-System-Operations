"""Python reference engine for differential testing and fallback."""

from __future__ import annotations

import struct
import uuid
from dataclasses import dataclass
from typing import Any

from circuit_breaker.models import Policy, ToolCall
from circuit_breaker.policy_engine import PolicyDecision, evaluate_policies_sync

from .compiler import parse_blob


@dataclass
class AoCall:
    agent_id: str
    tool: str
    input: str | None
    tokens: int
    cost_micro: int
    now_ns: int
    minute_of_day: int
    weekday: int
    risk_score_micro: int = 0
    anomaly_score_micro: int = 0


@dataclass
class AoResult:
    verdict: int
    reason_code: int
    policy_index: int
    retry_after_ms: int


_REASON_CODES = {
    "tool_allowlist": 2,
    "tool_blocklist": 1,
    "rate_limit": 3,
    "token_budget": 4,
    "risk_threshold": 5,
    "anomaly_threshold": 6,
    "time_window": 7,
    "reasoning_loop": 8,
}

_ACTION_IDS = {"allow": 0, "block": 1, "reroute": 2, "kill": 3, "alert": 4}


@dataclass
class _State:
    call_count: int = 0
    total_tokens: int = 0
    consecutive_same_tool: int = 0
    last_tool: str = ""


class PyEngine:
    def __init__(self) -> None:
        self._policies: list[Policy] = []
        self._window_seconds: list[int] = []
        self._states: dict[str, _State] = {}

    def load_policy(self, compiled: bytes) -> None:
        self._states.clear()
        self._policies = []
        self._window_seconds = []
        for idx, (typ, action, body) in enumerate(parse_blob(compiled)):
            typ_name = {
                1: "tool_allowlist",
                2: "tool_blocklist",
                3: "rate_limit",
                4: "token_budget",
                5: "risk_threshold",
                6: "anomaly_threshold",
                7: "time_window",
                8: "reasoning_loop",
            }.get(typ)
            if typ_name is None:
                raise ValueError(f"bad type {typ}")
            conds: dict[str, Any] = {}
            window = 3600
            if typ in {1, 2}:
                n = struct.unpack_from("<H", body, 0)[0]
                pos = 2
                pats = []
                for _ in range(n):
                    length = struct.unpack_from("<H", body, pos)[0]
                    pos += 2
                    pats.append(body[pos : pos + length].decode())
                    pos += length
                conds["tools"] = pats
            elif typ in {3, 4}:
                val, window = struct.unpack_from("<II", body, 0)
                if typ == 3:
                    conds["max_calls"] = val
                    conds["window_seconds"] = window
                else:
                    conds["max_tokens"] = val
                    conds["window_seconds"] = window
            elif typ in {5, 6}:
                val = struct.unpack_from("<Q", body, 0)[0]
                if typ == 5:
                    conds["max_risk_score"] = val / 1_000_000.0
                else:
                    conds["max_anomaly_score"] = val / 1_000_000.0
            elif typ == 7:
                start, end = struct.unpack_from("<II", body, 0)
                conds["start"] = start / 60.0
                conds["end"] = end / 60.0
            elif typ == 8:
                conds["max_consecutive_same_tool"] = struct.unpack_from("<I", body, 0)[0]
            action_name = {v: k for k, v in _ACTION_IDS.items()}.get(action, "block")
            policy = Policy(
                tenant_id=uuid.uuid4(),
                name=f"compiled-{idx}",
                policy_type=typ_name,
                conditions=conds,
                action=action_name,
                priority=len(self._policies),
            )
            self._policies.append(policy)
            self._window_seconds.append(window)

    def intercept(self, call: AoCall) -> AoResult:
        state = self._states.setdefault(call.agent_id, _State())
        state.call_count += 1
        state.total_tokens += call.tokens
        if call.tool == state.last_tool:
            state.consecutive_same_tool += 1
        else:
            state.consecutive_same_tool = 1
        state.last_tool = call.tool

        tc = ToolCall(
            tenant_id=uuid.uuid4(),
            agent_id=call.agent_id,
            tool_name=call.tool,
            tool_input={"input": call.input},
            token_count=call.tokens,
            cost=call.cost_micro / 1_000_000.0,
            risk_score=call.risk_score_micro / 1_000_000.0,
            anomaly_score=call.anomaly_score_micro / 1_000_000.0,
        )
        windowed = {
            "call_count": state.call_count,
            "total_tokens": state.total_tokens,
            "consecutive_same_tool": state.consecutive_same_tool,
        }
        decision: PolicyDecision = evaluate_policies_sync(
            self._policies, tc, windowed_stats=windowed
        )
        if not decision.allowed:
            idx = next(
                (i for i, p in enumerate(self._policies) if p.name == decision.policy_name), -1
            )
            typ = next(
                (p.policy_type for p in self._policies if p.name == decision.policy_name), ""
            )
            code = _REASON_CODES.get(typ, 0)
            retry = 3600000 if typ == "rate_limit" else 0
            return AoResult(verdict=2, reason_code=code, policy_index=idx, retry_after_ms=retry)
        return AoResult(verdict=0, reason_code=0, policy_index=-1, retry_after_ms=0)
