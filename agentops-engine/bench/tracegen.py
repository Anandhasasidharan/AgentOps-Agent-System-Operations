"""Deterministic seeded trace generator for AgentOps engine benchmarks."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class TraceCall:
    agent_id: str
    tool: str
    input: str | None
    tokens: int
    cost_micro: int
    now_ns: int
    minute_of_day: int
    weekday: int
    call_count: int
    total_tokens: int
    consecutive_same_tool: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


_AGENTS = [f"agent-{i}" for i in range(8)]
_TOOLS = ["read_file", "list_files", "search", "write_file", "delete_file", "execute_command", "http_request", "run_sql"]
_BLOCKED = {"delete_file", "execute_command", "drop_table"}
_BLOCKED_PATTERNS = ["rm -rf", "DELETE FROM", "curl | sh", "$("]


def _rng_from_seed(seed: int) -> random.Random:
    return random.Random(seed)


def iter_trace(seed: int, calls: int) -> Iterator[TraceCall]:
    rng = _rng_from_seed(seed)
    per_agent: dict[str, dict[str, int]] = {}
    base_ns = 1_700_000_000_000_000_000
    for i in range(calls):
        agent_id = rng.choice(_AGENTS)
        profile = per_agent.setdefault(agent_id, {"call_count": 0, "total_tokens": 0, "last_tool": "", "same": 0})
        profile["call_count"] += 1
        burst = profile["call_count"] % 90 < 25
        if burst and rng.random() < 0.7:
            tool = rng.choice(["search", "read_file", "http_request"])
        else:
            tool = rng.choice(_TOOLS)
        same = profile["same"] + 1 if tool == profile["last_tool"] else 1
        profile["last_tool"] = tool
        profile["same"] = same
        tokens = rng.randint(1, 5000) if tool in {"search", "http_request"} else rng.randint(1, 500)
        profile["total_tokens"] += tokens
        dangerous = tool in _BLOCKED or any(p in (tool or "") for p in []) or rng.random() < 0.03
        input_term = "benign"
        if dangerous:
            input_term = rng.choice(_BLOCKED_PATTERNS)
        now_ns = base_ns + i * 1_000_000_000 + rng.randint(0, 999_999_999)
        minute_of_day = (now_ns // 60_000_000_000) % (24 * 60)
        weekday = (now_ns // (86_400_000_000_000)) % 7
        yield TraceCall(
            agent_id=agent_id,
            tool=tool,
            input=input_term,
            tokens=tokens,
            cost_micro=tokens * 3,
            now_ns=now_ns,
            minute_of_day=int(minute_of_day),
            weekday=int(weekday),
            call_count=profile["call_count"],
            total_tokens=profile["total_tokens"],
            consecutive_same_tool=same,
        )


def write_trace(path: Path, seed: int, calls: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for call in iter_trace(seed, calls):
            f.write(call.to_json() + "\n")


def replay_trace(path: Path) -> Iterator[TraceCall]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield TraceCall(**json.loads(line))
