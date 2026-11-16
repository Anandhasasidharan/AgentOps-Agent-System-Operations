"""Benchmark runner for the current Python policy engine.

Usage: python -m bench.run --engine py --calls 100000 --seed 1
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import statistics
import sys
import time
import tracemalloc
import uuid
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.tracegen import TraceCall, iter_trace, write_trace


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _summarize(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "mean_ms": statistics.mean(values) if values else 0.0,
        "calls_per_sec": len(values) / (sum(values) / 1000.0) if values else 0.0,
    }


async def _bench_policy_engine(calls: int, seed: int) -> dict[str, Any]:
    from circuit_breaker.models import Policy, ToolCall
    from circuit_breaker.policy_engine import evaluate_policies

    tenant_id = uuid.uuid4()
    policies = [
        Policy(tenant_id=tenant_id, name="block-dangerous", policy_type="tool_blocklist", conditions={"tools": ["delete_file", "execute_command", "drop_table"]}, action="block", priority=10),
        Policy(tenant_id=tenant_id, name="rate-100", policy_type="rate_limit", conditions={"max_calls": 100}, action="block", priority=5),
        Policy(tenant_id=tenant_id, name="tokens-100k", policy_type="token_budget", conditions={"max_tokens": 100000}, action="block", priority=4),
        Policy(tenant_id=tenant_id, name="loop", policy_type="reasoning_loop", conditions={"max_consecutive_same_tool": 5}, action="block", priority=3),
        Policy(tenant_id=tenant_id, name="risk", policy_type="risk_threshold", conditions={"max_risk_score": 0.9}, action="block", priority=2),
    ]
    latencies: list[float] = []
    for call in iter_trace(seed, calls):
        tc = ToolCall(
            tenant_id=tenant_id,
            agent_id=call.agent_id,
            tool_name=call.tool,
            tool_input={"input": call.input},
            token_count=call.tokens,
            cost=call.cost_micro / 1_000_000.0,
            risk_score=0.4,
            anomaly_score=0.3,
        )
        windowed = {
            "call_count": call.call_count,
            "total_tokens": call.total_tokens,
            "consecutive_same_tool": call.consecutive_same_tool,
        }
        t0 = time.perf_counter_ns()
        await evaluate_policies(None, tenant_id, tc, policies=policies, windowed_stats=windowed)
        latencies.append((time.perf_counter_ns() - t0) / 1_000_000.0)
    return _summarize(latencies)


async def _bench_e2e(calls: int, seed: int) -> dict[str, Any]:
    from circuit_breaker.api import app, get_db, get_tenant
    from circuit_breaker.models import Base, Policy
    from agentops_core.base import Tenant

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = SessionLocal()
    await session.__aenter__()
    tenant = Tenant(id=uuid.uuid4(), slug="bench", name="Bench")
    session.add(tenant)
    session.add_all([
        Policy(tenant_id=tenant.id, name="block-dangerous", policy_type="tool_blocklist", conditions={"tools": ["delete_file", "execute_command", "drop_table"]}, action="block", priority=10),
        Policy(tenant_id=tenant.id, name="rate-100", policy_type="rate_limit", conditions={"max_calls": 100}, action="block", priority=5),
    ])
    await session.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant] = lambda: tenant
    latencies: list[float] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://bench") as client:
        for call in iter_trace(seed, calls):
            payload = {
                "agent_id": call.agent_id,
                "session_id": None,
                "tool_name": call.tool,
                "tool_input": {"input": call.input},
                "duration_ms": 1.0,
                "token_count": call.tokens,
                "cost": call.cost_micro / 1_000_000.0,
            }
            t0 = time.perf_counter_ns()
            resp = await client.post("/v1/intercept", json=payload)
            latencies.append((time.perf_counter_ns() - t0) / 1_000_000.0)
            if resp.status_code >= 500:
                raise RuntimeError(f"intercept failed: {resp.status_code} {resp.text}")
    app.dependency_overrides.clear()
    await session.__aexit__(None, None, None)
    await engine.dispose()
    return _summarize(latencies)


async def main_async(args: argparse.Namespace) -> int:
    trace_path = Path(args.trace)
    write_trace(trace_path, args.seed, args.calls)
    started = time.perf_counter_ns()
    tracemalloc.start()
    if args.engine in ("py", "auto"):
        engine_stats = await _bench_policy_engine(args.calls, args.seed)
        e2e_stats = await _bench_e2e(min(args.calls, 20000), args.seed) if args.e2e_calls is None else await _bench_e2e(args.e2e_calls, args.seed)
    else:
        raise SystemExit("engine c not implemented in this prompt phase")
    elapsed = (time.perf_counter_ns() - started) / 1_000_000_000.0
    current, peak = tracemalloc.get_traced_memory()
    result = {
        "machine": {"platform": platform.platform(), "python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor()},
        "git_sha": _git_sha(),
        "calls": args.calls,
        "seed": args.seed,
        "trace": str(trace_path),
        "engine_only": engine_stats,
        "e2e_intercept": e2e_stats,
        "elapsed_sec": elapsed,
        "tracemalloc_peak_bytes": peak,
    }
    out = Path(args.output or f"bench/results/{args.engine}-phase1.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print("metric        p50_ms    p95_ms    p99_ms    calls/sec")
    for name, stats in (("engine_only", engine_stats), ("e2e_intercept", e2e_stats)):
        print(f"{name:14} {stats['p50_ms']:.4f}  {stats['p95_ms']:.4f}  {stats['p99_ms']:.4f}  {stats['calls_per_sec']:.1f}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _git_sha() -> str:
    try:
        import subprocess
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    p = argparse.ArgumentParser(prog="bench.run")
    p.add_argument("--engine", default="py", choices=["py", "c", "auto"])
    p.add_argument("--calls", type=int, default=100000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--trace", default="bench/results/trace-seed1.jsonl")
    p.add_argument("--output", default=None)
    p.add_argument("--e2e-calls", type=int, default=None)
    args = p.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
