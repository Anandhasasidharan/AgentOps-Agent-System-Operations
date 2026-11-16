"""Verify the running local development stack and create an isolated demo agent."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    key = (ROOT / ".agentops-runtime" / "api-key").read_text().strip()
    with httpx.Client(headers={"X-API-Key": key}, timeout=10) as client:

        def request(method, port, path, **kwargs):
            response = client.request(method, f"http://127.0.0.1:{port}{path}", **kwargs)
            response.raise_for_status()
            return response.json()

        for port in range(8000, 8005):
            assert request("GET", port, "/health")["status"] == "ok"
            client.get(f"http://127.0.0.1:{port}/metrics").raise_for_status()
            print(f"PASS service {port}: health and metrics", flush=True)
        health = request("GET", 8003, "/api/health")
        assert health["status"] == "ok", health
        print("PASS dashboard: four upstream services and NATS healthy", flush=True)
        agent = request(
            "POST", 8000, "/api/v1/agents", json={"name": f"local-check-{uuid.uuid4().hex[:8]}"}
        )
        slis = request("GET", 8000, "/api/v1/slis")
        sli = next((item for item in slis if item["name"] == "tool_accuracy"), None)
        if not sli:
            sli = request(
                "POST",
                8000,
                "/api/v1/slis",
                json={"name": "tool_accuracy", "metric_type": "ratio", "source": "otel"},
            )
        request(
            "POST",
            8000,
            "/api/v1/slos",
            json={
                "agent_id": agent["id"],
                "sli_id": sli["id"],
                "name": f"accuracy-{agent['name']}",
                "target": 0.95,
                "comparator": "gt",
                "window": "7d",
            },
        )
        request(
            "POST",
            8001,
            "/api/v1/policies",
            json={
                "name": f"protect-{agent['name']}",
                "policy_type": "tool_blocklist",
                "conditions": {"tools": ["delete_database"], "agent_id": agent["id"]},
                "action": "block",
            },
        )
        for tool, allowed in [("read_inventory", True), ("delete_database", False)]:
            result = request(
                "POST",
                8001,
                "/v1/intercept",
                json={"agent_id": agent["id"], "tool_name": tool, "tool_input": {}},
            )
            assert result["allowed"] is allowed
            print(f"PASS {tool}: {result['decision']}", flush=True)
        # Poll policies, not SLO status: enforcement must come from the scheduler.
        for _ in range(60):
            policies = request("GET", 8001, "/api/v1/policies")
            if any(p["name"] == f"auto-lockdown-{agent['id']}" for p in policies):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Scheduled SLO lockdown did not arrive")
        result = request(
            "POST",
            8001,
            "/v1/intercept",
            json={"agent_id": agent["id"], "tool_name": "read_inventory", "tool_input": {}},
        )
        assert result["allowed"] is False
        events = request("GET", 8004, "/api/v1/events")
        assert any(e["event_type"].startswith("agentops.slo.breach.") for e in events)
        print(
            "PASS authenticated telemetry -> scheduled SLO breach -> NATS -> agent lockdown",
            flush=True,
        )
        print(
            "Dashboard: http://localhost:8003 (any username; password in .agentops-runtime/api-key)"
        )


if __name__ == "__main__":
    main()
