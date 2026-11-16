"""Verify the public five-service SLO-to-lockdown workflow.

Requires make setup and NATS_SERVER_BINARY pointing to a local nats-server.
Uses disposable SQLite, localhost ports, and generated tenant credentials.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

import httpx

from agentops_core.telemetry import emit_tool_call_span
from guarded_agent import free_port


async def main():
    processes = []
    with tempfile.TemporaryDirectory(prefix="agentops-workflow-") as directory:
        database = Path(directory) / "workflow.db"
        urls = {
            name: f"http://127.0.0.1:{free_port()}"
            for name in ("agent_slo", "circuit_breaker", "chaos_toolkit", "gateway", "dashboard")
        }
        nats_port = free_port()
        env = dict(os.environ)
        env.update(
            DATABASE_URL=f"sqlite+aiosqlite:///{database}",
            NATS_URL=f"nats://127.0.0.1:{nats_port}",
            RATE_LIMIT_RPM="0",
            SLO_EVALUATION_INTERVAL_SECONDS="0.25",
            SLO_URL=urls["agent_slo"],
            CB_URL=urls["circuit_breaker"],
            CHAOS_URL=urls["chaos_toolkit"],
            GATEWAY_URL=urls["gateway"],
            GATEWAY_PUBLIC_URL=urls["gateway"],
            OTEL_EXPORTER_ENDPOINT=urls["agent_slo"] + "/v1/traces",
        )
        with (Path(directory) / "services.log").open("w+") as log:
            try:
                processes.append(
                    subprocess.Popen(
                        [
                            env["NATS_SERVER_BINARY"],
                            "-js",
                            "-sd",
                            directory + "/nats",
                            "-a",
                            "127.0.0.1",
                            "-p",
                            str(nats_port),
                        ],
                        stdout=log,
                        stderr=log,
                    )
                )
                async with httpx.AsyncClient(timeout=10) as client:

                    async def start(name):
                        process = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "uvicorn",
                                name + ".api:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                urls[name].rsplit(":", 1)[1],
                            ],
                            env=env,
                            stdout=log,
                            stderr=log,
                        )
                        processes.append(process)
                        for _ in range(300):
                            if process.poll() is not None:
                                raise RuntimeError(f"{name} failed to start")
                            try:
                                if (await client.get(urls[name] + "/health")).status_code == 200:
                                    return
                            except httpx.HTTPError:
                                pass
                            await asyncio.sleep(0.2)
                        raise RuntimeError(f"{name} startup timed out")

                    async def request(method, service, path, **kwargs):
                        response = await client.request(method, urls[service] + path, **kwargs)
                        response.raise_for_status()
                        return response.json()

                    async def wait_metrics(count):
                        for _ in range(100):
                            with sqlite3.connect(database) as connection:
                                actual = connection.execute(
                                    "SELECT count(*) FROM metrics"
                                ).fetchone()[0]
                            if actual >= count:
                                return
                            await asyncio.sleep(0.1)
                        raise RuntimeError("Authenticated telemetry did not reach SLO metrics")

                    await start("agent_slo")
                    tenant = await request(
                        "POST",
                        "agent_slo",
                        "/api/v1/tenants",
                        json={"slug": "workflow", "name": "Public workflow verification"},
                    )
                    key = tenant["api_key"]
                    headers = {"X-API-Key": key}
                    env["API_KEY"] = key
                    for name in ("circuit_breaker", "chaos_toolkit", "gateway", "dashboard"):
                        await start(name)
                    for name in urls:
                        (await client.get(urls[name] + "/metrics")).raise_for_status()
                    assert (await client.get(urls["dashboard"] + "/")).status_code == 401
                    assert (
                        await client.get(urls["dashboard"] + "/", headers=headers)
                    ).status_code == 200
                    assert (await client.get(urls["gateway"] + "/api/v1/events")).status_code == 401
                    agent = await request(
                        "POST",
                        "agent_slo",
                        "/api/v1/agents",
                        headers=headers,
                        json={"name": "guarded"},
                    )
                    other = await request(
                        "POST",
                        "agent_slo",
                        "/api/v1/agents",
                        headers=headers,
                        json={"name": "unaffected"},
                    )
                    sli = await request(
                        "POST",
                        "agent_slo",
                        "/api/v1/slis",
                        headers=headers,
                        json={"name": "tool_accuracy", "metric_type": "ratio", "source": "otel"},
                    )
                    verdict = await request(
                        "POST",
                        "circuit_breaker",
                        "/v1/intercept",
                        headers=headers,
                        json={
                            "agent_id": agent["id"],
                            "tool_name": "read_inventory",
                            "tool_input": {},
                        },
                    )
                    assert verdict["allowed"] is True
                    await wait_metrics(1)
                    print(
                        "PASS: all five services, authentication, and automatic authenticated telemetry",
                        flush=True,
                    )
                    slo = await request(
                        "POST",
                        "agent_slo",
                        "/api/v1/slos",
                        headers=headers,
                        json={
                            "name": "95-percent-tool-accuracy",
                            "sli_id": sli["id"],
                            "agent_id": agent["id"],
                            "target": 0.95,
                            "comparator": "gt",
                            "window": "7d",
                        },
                    )
                    assert slo["agent_id"] == agent["id"]
                    status = await request(
                        "GET",
                        "agent_slo",
                        "/api/v1/status",
                        headers=headers,
                        params={"agent_id": agent["id"]},
                    )
                    assert len(status) == 1 and status[0]["is_breaching"] is False
                    # No status polling from here: only the scheduled worker can publish the breach.
                    await emit_tool_call_span(
                        urls["agent_slo"] + "/v1/traces", key, agent["id"], "failed_tool", True
                    )
                    await wait_metrics(2)
                    for _ in range(100):
                        policies = await request(
                            "GET", "circuit_breaker", "/api/v1/policies", headers=headers
                        )
                        if any(p["conditions"].get("agent_id") == agent["id"] for p in policies):
                            break
                        await asyncio.sleep(0.1)
                    else:
                        raise RuntimeError("Scheduled SLO breach did not create a lockdown")
                    for identity, allowed in [(agent["id"], False), (other["id"], True)]:
                        verdict = await request(
                            "POST",
                            "circuit_breaker",
                            "/v1/intercept",
                            headers=headers,
                            json={
                                "agent_id": identity,
                                "tool_name": "read_inventory",
                                "tool_input": {},
                            },
                        )
                        assert verdict["allowed"] is allowed
                    events = await request("GET", "gateway", "/api/v1/events", headers=headers)
                    assert any(e["event_type"].startswith("agentops.slo.breach.") for e in events)
                    print(
                        "PASS: API-created scoped SLO -> scheduled breach -> NATS -> lockdown -> blocked call",
                        flush=True,
                    )
                    print("PASS: other agent remains allowed; gateway receives breach", flush=True)
            except Exception:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == "__main__":
    asyncio.run(main())
