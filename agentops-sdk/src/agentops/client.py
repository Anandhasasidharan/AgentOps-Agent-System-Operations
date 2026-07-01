"""HTTP client for all 3 AgentOps platform APIs."""

from __future__ import annotations

import uuid
from typing import Any

import httpx


class AgentOpsSDK:
    """Unified client for Circuit Breaker, Chaos Toolkit, and SLO Platform."""

    def __init__(
        self,
        api_key: str,
        cb_url: str = "http://localhost:8001",
        chaos_url: str = "http://localhost:8002",
        slo_url: str = "http://localhost:8000",
        timeout: float = 10.0,
    ):
        self._headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self._cb_url = cb_url.rstrip("/")
        self._chaos_url = chaos_url.rstrip("/")
        self._slo_url = slo_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def close(self) -> None:
        await self._client.aclose()

    # ─── Tenant ──────────────────────────────────────────────────────────────

    async def create_tenant(self, slug: str, name: str) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._slo_url}/api/v1/tenants",
            json={"slug": slug, "name": name},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        return r.json()

    # ─── Circuit Breaker ──────────────────────────────────────────────────────

    async def intercept(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
        session_id: str | None = None,
        tool_output: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        token_count: int | None = None,
        cost: float | None = None,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._cb_url}/v1/intercept",
            json={
                "agent_id": agent_id,
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output,
                "duration_ms": duration_ms,
                "token_count": token_count,
                "cost": cost,
            },
        )
        r.raise_for_status()
        return r.json()

    async def create_policy(
        self,
        name: str,
        policy_type: str,
        conditions: dict[str, Any],
        action: str = "block",
        description: str | None = None,
        priority: int = 0,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._cb_url}/api/v1/policies",
            json={
                "name": name,
                "description": description,
                "enabled": True,
                "priority": priority,
                "policy_type": policy_type,
                "conditions": conditions,
                "action": action,
            },
        )
        r.raise_for_status()
        return r.json()

    async def list_policies(self) -> list[dict[str, Any]]:
        r = await self._client.get(f"{self._cb_url}/api/v1/policies")
        r.raise_for_status()
        return r.json()

    async def activate_kill_switch(
        self, agent_id: str, reason: str = "SDK kill signal"
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._cb_url}/api/v1/kill-switch/{agent_id}/activate",
            params={"reason": reason},
        )
        r.raise_for_status()
        return r.json()

    async def release_kill_switch(self, agent_id: str) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._cb_url}/api/v1/kill-switch/{agent_id}/release"
        )
        r.raise_for_status()
        return r.json()

    async def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        r = await self._client.get(
            f"{self._cb_url}/api/v1/agents/{agent_id}/status"
        )
        r.raise_for_status()
        return r.json()

    # ─── Chaos Toolkit ─────────────────────────────────────────────────────────

    async def seed_scenarios(self) -> list[dict[str, Any]]:
        r = await self._client.post(f"{self._chaos_url}/api/v1/scenarios/seed")
        r.raise_for_status()
        return r.json()

    async def list_scenarios(
        self, target_type: str | None = None
    ) -> list[dict[str, Any]]:
        params = {"target_type": target_type} if target_type else None
        r = await self._client.get(
            f"{self._chaos_url}/api/v1/scenarios", params=params
        )
        r.raise_for_status()
        return r.json()

    async def run_experiment(
        self,
        scenario_id: str | uuid.UUID,
        agent_id: str,
        target_override: str | None = None,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._chaos_url}/api/v1/experiments",
            json={
                "scenario_id": str(scenario_id),
                "agent_id": agent_id,
                "target_override": target_override,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_resilience_score(self) -> dict[str, Any]:
        r = await self._client.get(f"{self._chaos_url}/api/v1/resilience-score")
        r.raise_for_status()
        return r.json()

    # ─── SLO Platform ──────────────────────────────────────────────────────────

    async def create_agent(
        self,
        name: str,
        environment: str = "production",
        framework: str | None = None,
        model_provider: str | None = None,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._slo_url}/api/v1/agents",
            json={
                "name": name,
                "environment": environment,
                "framework": framework,
                "model_provider": model_provider,
            },
        )
        r.raise_for_status()
        return r.json()

    async def create_sli(
        self,
        name: str,
        metric_type: str,
        source: str = "otel",
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._slo_url}/api/v1/slis",
            json={
                "name": name,
                "metric_type": metric_type,
                "source": source,
                "config": config or {},
            },
        )
        r.raise_for_status()
        return r.json()

    async def create_slo(
        self,
        sli_id: str | uuid.UUID,
        name: str,
        target: float,
        comparator: str = "gt",
        window: str = "30d",
        description: str | None = None,
    ) -> dict[str, Any]:
        r = await self._client.post(
            f"{self._slo_url}/api/v1/slos",
            json={
                "sli_id": str(sli_id),
                "name": name,
                "description": description,
                "target": target,
                "comparator": comparator,
                "window": window,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_status(self) -> list[dict[str, Any]]:
        r = await self._client.get(f"{self._slo_url}/api/v1/status")
        r.raise_for_status()
        return r.json()

    # ─── Convenience ───────────────────────────────────────────────────────────

    async def send_otel_span(
        self,
        agent_id: str,
        success: bool = True,
        duration_ms: float = 150.0,
        input_tokens: int = 450,
        output_tokens: int = 120,
    ) -> dict[str, Any]:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": agent_id}},
                            {"key": "agentops.agent.id", "value": {"stringValue": agent_id}},
                            {"key": "agentops.environment", "value": {"stringValue": "production"}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": trace_id,
                                    "spanId": span_id,
                                    "name": "task-execution",
                                    "kind": 2,
                                    "startTimeUnixNano": "0",
                                    "endTimeUnixNano": str(int(duration_ms * 1_000_000)),
                                    "attributes": [
                                        {"key": "gen_ai.eval.success", "value": {"intValue": "1" if success else "0"}},
                                        {"key": "gen_ai.eval.total", "value": {"intValue": "1"}},
                                        {"key": "gen_ai.tool.success", "value": {"intValue": "1"}},
                                        {"key": "gen_ai.tool.calls", "value": {"intValue": "1"}},
                                        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(input_tokens)}},
                                        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": str(output_tokens)}},
                                        {"key": "gen_ai.response.duration", "value": {"intValue": str(int(duration_ms))}},
                                    ],
                                    "status": {"code": 1 if success else 2},
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        r = await self._client.post(f"{self._slo_url}/v1/traces", json=payload)
        r.raise_for_status()
        return r.json()

    async def setup_demo(self, slug: str = "demo") -> dict[str, Any]:
        """One-shot demo setup: create tenant, agent, SLI, SLO, policy, seed scenarios."""
        results: dict[str, Any] = {}
        tenant = await self.create_tenant(slug=slug, name="Demo Tenant")
        results["tenant"] = tenant

        agent = await self.create_agent(name="demo-agent")
        results["agent"] = agent

        sli = await self.create_sli(name="task-success-rate", metric_type="ratio")
        results["sli"] = sli

        slo = await self.create_slo(
            sli_id=sli["id"], name="95% success rate", target=0.95
        )
        results["slo"] = slo

        policy = await self.create_policy(
            name="block-dangerous-commands",
            policy_type="tool_blocklist",
            conditions={"tools": ["rm", "dd", "mkfs"]},
        )
        results["policy"] = policy

        scenarios = await self.seed_scenarios()
        results["scenarios_count"] = len(scenarios)

        return results
