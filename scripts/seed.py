"""Seed the AgentOps platform with demo data.

Usage:
    python scripts/seed.py

Prerequisites:
    docker compose up  (all 4 services running)

Environment variables (all optional):
    CB_URL=http://localhost:8001
    CHAOS_URL=http://localhost:8002
    SLO_URL=http://localhost:8000
    API_KEY=dev-api-key
"""

import os
import sys
import time
import uuid
import httpx

CB_URL = os.getenv("CB_URL", "http://localhost:8001")
CHAOS_URL = os.getenv("CHAOS_URL", "http://localhost:8002")
SLO_URL = os.getenv("SLO_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8004")

HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
PASS = "✓"
FAIL = "✗"


def wait_for(url: str, name: str, retries: int = 30, delay: float = 1.0) -> bool:
    for i in range(retries):
        try:
            r = httpx.get(f"{url}/health", timeout=3)
            if r.status_code == 200:
                print(f"  {PASS} {name} ready ({url})")
                return True
        except httpx.RequestError:
            pass
        time.sleep(delay)
    print(f"  {FAIL} {name} not ready after {retries * delay}s ({url})")
    return False


def post(url: str, json: dict | None = None, headers: dict | None = None) -> httpx.Response:
    h = headers or HEADERS
    return httpx.post(url, json=json, headers=h, timeout=10)


def get(url: str, headers: dict | None = None) -> httpx.Response:
    return httpx.get(url, headers=headers or HEADERS, timeout=10)


def main() -> int:
    global API_KEY
    print("\n=== AgentOps — Seed Demo Data ===\n")

    # 1. Wait for all services
    print("Waiting for services...")
    ok = all([
        wait_for(SLO_URL, "SLO Platform"),
        wait_for(CB_URL, "Circuit Breaker"),
        wait_for(CHAOS_URL, "Chaos Toolkit"),
    ])
    if not ok:
        print(f"\n{FAIL} Some services not available. Is `docker compose up` running?")
        return 1
    print()

    # 2. Create tenant (unauthenticated)
    print("Creating tenant...")
    r = post(f"{SLO_URL}/api/v1/tenants",
             json={"slug": API_KEY.split(":")[0], "name": "Acme Corp"},
             headers={"Content-Type": "application/json"})
    if r.status_code == 201:
        data = r.json()
        if data.get("api_key"):
            API_KEY = data["api_key"]
            HEADERS["X-API-Key"] = API_KEY
        print(f"  {PASS} Tenant '{API_KEY.split(':')[0]}' created (key: {API_KEY[:20]}...)")
    elif r.status_code == 409:
        print(f"  {PASS} Tenant '{API_KEY.split(':')[0]}' already exists")
    else:
        print(f"  {FAIL} Create tenant: {r.status_code} {r.text[:200]}")
        return 1

    # 3. Create agent
    print("Creating agent...")
    r = post(f"{SLO_URL}/api/v1/agents", json={
        "name": "demo-agent",
        "environment": "production",
        "framework": "langchain",
        "model_provider": "openai",
    })
    if r.status_code == 200:
        agent = r.json()
        print(f"  {PASS} Agent 'demo-agent' created (id={agent['id']})")
    else:
        print(f"  {FAIL} Create agent: {r.status_code} {r.text[:200]}")
        return 1

    # 4. Create SLI
    print("Creating SLI...")
    r = post(f"{SLO_URL}/api/v1/slis", json={
        "name": "task-success-rate",
        "metric_type": "ratio",
        "source": "otel",
        "config": {},
    })
    if r.status_code == 200:
        sli = r.json()
        print(f"  {PASS} SLI 'task-success-rate' created (id={sli['id']})")
    else:
        print(f"  {FAIL} Create SLI: {r.status_code} {r.text[:200]}")
        return 1

    # 5. Create SLO
    print("Creating SLO...")
    r = post(f"{SLO_URL}/api/v1/slos", json={
        "sli_id": str(sli["id"]),
        "name": "95% task success (30d rolling)",
        "description": "Demo SLO: agents must complete 95% of tasks successfully over a 30-day rolling window",
        "target": 0.95,
        "comparator": "gt",
        "window": "30d",
        "labels": {"env": "production", "team": "platform"},
    })
    if r.status_code == 200:
        slo = r.json()
        print(f"  {PASS} SLO created (id={slo['id']}, target=95%)")
    else:
        print(f"  {FAIL} Create SLO: {r.status_code} {r.text[:200]}")
        return 1

    # 6. Seed chaos scenarios
    print("Seeding chaos scenarios...")
    r = post(f"{CHAOS_URL}/api/v1/scenarios/seed")
    if r.status_code == 200:
        count = len(r.json())
        print(f"  {PASS} {count} built-in chaos scenarios seeded")
    elif r.status_code == 409:
        print(f"  {PASS} Chaos scenarios already seeded")
    else:
        print(f"  ({r.status_code}) {r.text[:200]}")

    # 7. Get a scenario ID for demo experiment
    print("Fetching chaos scenarios...")
    r = get(f"{CHAOS_URL}/api/v1/scenarios")
    scenarios = r.json() if r.status_code == 200 else []
    if scenarios:
        scenario_id = scenarios[0]["id"]
        print(f"  {PASS} Using scenario '{scenarios[0]['name']}' ({scenario_id})")
    else:
        print(f"  {FAIL} No scenarios available")
        scenario_id = None

    # 8. Run a chaos experiment
    if scenario_id:
        print("Running chaos experiment...")
        r = post(f"{CHAOS_URL}/api/v1/experiments", json={
            "scenario_id": str(scenario_id),
            "agent_id": "demo-agent",
        })
        if r.status_code == 200:
            exp = r.json()
            print(f"  {PASS} Experiment started (id={exp['id']}, status={exp.get('status', 'running')})")
        else:
            print(f"  {FAIL} Run experiment: {r.status_code} {r.text[:200]}")

    # 9. Create a policy (block dangerous commands)
    print("Creating circuit breaker policy...")
    r = post(f"{CB_URL}/api/v1/policies", json={
        "name": "block-dangerous-commands",
        "description": "Block filesystem-destructive tools from running",
        "enabled": True,
        "priority": 100,
        "policy_type": "tool_blocklist",
        "conditions": {
            "tools": ["rm", "rmdir", "dd", "mkfs", "shutdown", "reboot", "kill", "pkill"],
        },
        "action": "block",
        "action_config": {"reason": "Dangerous filesystem command blocked by policy"},
    })
    if r.status_code == 200:
        policy = r.json()
        print(f"  {PASS} Policy 'block-dangerous-commands' created (id={policy['id']})")
    elif r.status_code == 409:
        print(f"  {PASS} Policy already exists")
    else:
        print(f"  {FAIL} Create policy: {r.status_code} {r.text[:200]}")

    # 10. Send safe tool call via circuit breaker
    print("Sending safe tool call...")
    r = post(f"{CB_URL}/v1/intercept", json={
        "agent_id": "demo-agent",
        "session_id": f"session-{uuid.uuid4().hex[:8]}",
        "tool_name": "read_file",
        "tool_input": {"path": "/tmp/test.txt"},
        "tool_output": {"content": "hello world", "size_bytes": 11},
        "duration_ms": 150.0,
        "token_count": 50,
    })
    if r.status_code == 200:
        result = r.json()
        decision = result.get("decision", "unknown")
        print(f"  {PASS} Safe tool call -> {decision}")
    else:
        print(f"  ({r.status_code}) read_file: {r.text[:200]}")

    # 11. Send blocked tool call
    print("Sending blocked tool call...")
    r = post(f"{CB_URL}/v1/intercept", json={
        "agent_id": "demo-agent",
        "session_id": f"session-{uuid.uuid4().hex[:8]}",
        "tool_name": "rm",
        "tool_input": {"path": "/", "recursive": True, "force": True},
        "duration_ms": 0.5,
        "token_count": 10,
    })
    if r.status_code == 200:
        result = r.json()
        decision = result.get("decision", "unknown")
        print(f"  {PASS} Blocked tool call -> {decision}")
    else:
        print(f"  ({r.status_code}) rm: {r.text[:200]}")

    # 12. Send OTel trace span to SLO
    print("Sending OTel trace span...")
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    r = post(f"{SLO_URL}/v1/traces", json={
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "demo-agent"}},
                    {"key": "agentops.agent.id", "value": {"stringValue": "demo-agent"}},
                    {"key": "agentops.environment", "value": {"stringValue": "production"}},
                ]
            },
            "scopeSpans": [{
                "spans": [{
                    "traceId": trace_id,
                    "spanId": span_id,
                    "name": "task-execution",
                    "kind": 2,
                    "startTimeUnixNano": str(int(time.time() * 1_000_000_000)),
                    "endTimeUnixNano": str(int(time.time() * 1_000_000_000) + 150_000_000),
                    "attributes": [
                        {"key": "gen_ai.eval.success", "value": {"intValue": "1"}},
                        {"key": "gen_ai.eval.total", "value": {"intValue": "1"}},
                        {"key": "gen_ai.tool.success", "value": {"intValue": "1"}},
                        {"key": "gen_ai.tool.calls", "value": {"intValue": "1"}},
                        {"key": "gen_ai.usage.input_tokens", "value": {"intValue": "450"}},
                        {"key": "gen_ai.usage.output_tokens", "value": {"intValue": "120"}},
                        {"key": "gen_ai.response.duration", "value": {"intValue": "150"}},
                    ],
                    "status": {"code": 1},
                }]
            }]
        }]
    })
    if r.status_code in (200, 202):
        print(f"  {PASS} OTel span ingested by SLO")
    else:
        print(f"  ({r.status_code}) OTel: {r.text[:200]}")

    # Summary
    print(f"\n{'=' * 50}")
    print(f"  {PASS} Seed complete!")
    print(f"\n  Dashboard: http://localhost:8003")
    print(f"  API Key:   {API_KEY}")
    print(f"\n  Try these CLIs:")
    print(f"    cbctl    status --api-key {API_KEY}")
    print(f"    chaosctl status --api-key {API_KEY}")
    print(f"    sloctl   status --api-key {API_KEY}")
    print(f"{'=' * 50}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
