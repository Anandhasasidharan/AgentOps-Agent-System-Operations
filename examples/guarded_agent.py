"""Run a real HTTP enforcement demo without Docker, an LLM, or paid API keys.

Requires the packages installed by make setup. Temporary SQLite data is deleted
on exit. Tools are harmless Python functions; the blocked function must not run.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import uuid

import httpx


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def wait_ready(client, url, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Service exited during startup")
        try:
            response = await client.get(f"{url}/health")
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.2)
    raise RuntimeError(f"Service did not become ready: {url}")


async def main():
    from agentops import AgentOpsSDK, AgentOpsUnavailableError

    processes = []
    with tempfile.TemporaryDirectory(prefix="agentops-demo-") as directory:
        env = dict(os.environ)
        env.update(
            DATABASE_URL=f"sqlite+aiosqlite:///{directory}/demo.db",
            NATS_URL="",
            OTEL_EXPORTER_ENDPOINT="",
            RATE_LIMIT_RPM="0",
            SLO_EVALUATION_INTERVAL_SECONDS="0",
        )
        with (Path(directory) / "services.log").open("w+") as log:
            try:
                async with httpx.AsyncClient(timeout=5) as http:
                    urls = []
                    for module in ("agent_slo", "circuit_breaker"):
                        port = free_port()
                        url = f"http://127.0.0.1:{port}"
                        process = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "uvicorn",
                                f"{module}.api:app",
                                "--host",
                                "127.0.0.1",
                                "--port",
                                str(port),
                            ],
                            env=env,
                            stdout=log,
                            stderr=log,
                        )
                        processes.append(process)
                        await wait_ready(http, url, process)
                        urls.append(url)
                    slo_url, cb_url = urls
                    response = await http.post(
                        f"{slo_url}/api/v1/tenants",
                        json={"slug": f"demo-{uuid.uuid4().hex[:8]}", "name": "Guarded demo"},
                    )
                    response.raise_for_status()
                    key = response.json()["api_key"]
                    headers = {"X-API-Key": key}
                    response = await http.post(
                        f"{slo_url}/api/v1/agents", headers=headers, json={"name": "guarded-agent"}
                    )
                    response.raise_for_status()
                    agent_id = response.json()["id"]
                    response = await http.post(
                        f"{cb_url}/api/v1/policies",
                        headers=headers,
                        json={
                            "name": "protect-data",
                            "policy_type": "tool_blocklist",
                            "conditions": {"tools": ["delete_database"]},
                            "action": "block",
                        },
                    )
                    response.raise_for_status()
                    executed = []
                    for tool in ("read_inventory", "delete_database"):
                        response = await http.post(
                            f"{cb_url}/v1/intercept",
                            headers=headers,
                            json={"agent_id": agent_id, "tool_name": tool, "tool_input": {}},
                        )
                        response.raise_for_status()
                        verdict = response.json()
                        if verdict["allowed"]:
                            executed.append(tool)
                        print(f"{tool}: {verdict['decision']}")
                    if executed != ["read_inventory"]:
                        raise RuntimeError("Tool enforcement failed")
                    processes[-1].terminate()
                    processes[-1].wait(timeout=10)
                    sdk = AgentOpsSDK(api_key=key, cb_url=cb_url, fail_mode="closed")
                    try:
                        try:
                            await sdk.intercept(agent_id, "read_inventory", {})
                        except AgentOpsUnavailableError:
                            print("Breaker unavailable: denied (fail closed)")
                        else:
                            raise RuntimeError("Unavailable breaker did not fail closed")
                    finally:
                        await sdk.close()
                    print("PASS: safe tool ran; dangerous tool and outage were blocked")
            except Exception:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == "__main__":
    asyncio.run(main())
