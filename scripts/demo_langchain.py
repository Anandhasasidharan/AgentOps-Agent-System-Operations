#!/usr/bin/env python3
"""Demo: AgentOps platform with LangChain integration."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_KEY = os.getenv("AGENTOPS_API_KEY", "dev-api-key")
SLO_URL = os.getenv("AGENTOPS_SLO_URL", "http://localhost:8000")
CB_URL = os.getenv("AGENTOPS_CB_URL", "http://localhost:8001")
CHAOS_URL = os.getenv("AGENTOPS_CHAOS_URL", "http://localhost:8002")


async def check_health() -> dict:
    import httpx

    results = {}
    async with httpx.AsyncClient() as c:
        for name, url in [
            ("SLO Platform", f"{SLO_URL}/health"),
            ("Circuit Breaker", f"{CB_URL}/health"),
            ("Chaos Toolkit", f"{CHAOS_URL}/health"),
        ]:
            try:
                r = await c.get(url, timeout=5)
                results[name] = r.json().get("status", "error")
            except Exception as e:
                results[name] = f"unreachable ({e})"
    return results


async def setup_tenant() -> str:
    import httpx

    global API_KEY
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SLO_URL}/api/v1/tenants",
            json={"slug": API_KEY.split(":")[0] if ":" in API_KEY else API_KEY, "name": "Demo Tenant"},
        )
        if r.status_code == 201:
            data = r.json()
            if data.get("api_key"):
                API_KEY = data["api_key"]
            print("  tenant created")
        elif r.status_code == 409:
            print("  tenant already exists")
        else:
            print(f"  tenant setup: {r.status_code} {r.text[:100]}")
    return API_KEY


async def setup_policy():
    import httpx

    async with httpx.AsyncClient(headers={"X-API-Key": API_KEY}) as c:
        r = await c.post(
            f"{CB_URL}/api/v1/policies",
            json={
                "name": "block-rm",
                "policy_type": "tool_blocklist",
                "conditions": {"tools": ["rm", "bash", "exec_command"]},
                "action": "block",
                "enabled": True,
                "priority": 50,
            },
        )
        if r.status_code == 201:
            print("  policy created: block-rm")
        else:
            print(f"  policy: {r.status_code} {r.text[:100]}")


async def demo_wrap_tool():
    try:
        from agentops_langchain import wrap_tool
    except ImportError:
        print("  SKIP: agentops-langchain not installed")
        return

    def safe_tool(query: str) -> str:
        return f"searched: {query}"

    def dangerous_tool(cmd: str) -> str:
        return f"ran: {cmd}"

    wrapped_safe = wrap_tool(safe_tool, "search", API_KEY, CB_URL, "demo-agent")
    wrapped_dangerous = wrap_tool(
        dangerous_tool, "rm", API_KEY, CB_URL, "demo-agent"
    )

    print("  safe tool (search):", end=" ")
    try:
        result = wrapped_safe("hello")
        print(result)
    except Exception as e:
        print(f"BLOCKED: {e}")

    print("  blocked tool (rm):", end=" ")
    try:
        result = wrapped_dangerous("/etc")
        print(result)
    except Exception as e:
        print(f"BLOCKED: {e}")


async def demo_chaos():
    import httpx

    async with httpx.AsyncClient(headers={"X-API-Key": API_KEY}) as c:
        r = await c.post(f"{CHAOS_URL}/api/v1/scenarios/seed")
        scenarios = r.json() if r.status_code == 201 else []
        print(f"  seeded {len(scenarios)} chaos scenarios")

        if scenarios:
            r = await c.post(
                f"{CHAOS_URL}/api/v1/experiments",
                json={
                    "scenario_id": str(scenarios[0]["id"]),
                    "agent_id": "demo-agent",
                },
            )
            exp = r.json() if r.status_code == 201 else {}
            print(f"  experiment: {exp.get('status', 'failed')}")

        r = await c.get(f"{CHAOS_URL}/api/v1/resilience-score")
        score = r.json()
        print(f"  resilience: {score.get('avg_resilience_score', 0):.1%}")


async def demo_sdk():
    try:
        from agentops import AgentOpsSDK
    except ImportError:
        print("  SKIP: agentops-sdk not installed")
        return

    sdk = AgentOpsSDK(api_key=API_KEY, slo_url=SLO_URL, cb_url=CB_URL, chaos_url=CHAOS_URL)
    sdk_setup = await sdk.setup_demo()
    print(f"  SDK demo: {len(sdk_setup)} resources created")
    await sdk.close()


async def main():
    print("=== AgentOps Demo ===")
    print()

    print("1. Health checks...")
    health = await check_health()
    for name, status in health.items():
        print(f"  {name}: {status}")
    print()

    print("2. Setup...")
    await setup_tenant()
    await setup_policy()
    print()

    print("3. Tool wrapping demo...")
    await demo_wrap_tool()
    print()

    print("4. Chaos resilience demo...")
    await demo_chaos()
    print()

    print("5. SDK demo...")
    await demo_sdk()
    print()

    print("=== Demo complete ===")


if __name__ == "__main__":
    asyncio.run(main())
