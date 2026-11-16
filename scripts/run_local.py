"""Start, inspect, or stop the local development stack without Docker.

Uses SQLite and a local nats-server; production uses PostgreSQL/Compose.
Runtime data and credentials live under .agentops-runtime (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".agentops-runtime"
STATE = RUNTIME / "processes.json"
SERVICES = {
    "slo": ("agent_slo", 8000),
    "breaker": ("circuit_breaker", 8001),
    "chaos": ("chaos_toolkit", 8002),
    "gateway": ("gateway", 8004),
    "dashboard": ("dashboard", 8003),
}


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] in ("Z", "X") else fields[19]
    except (OSError, IndexError):
        return None


def running(record):
    return identity(record["pid"]) == record["identity"] and record["identity"] is not None


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def stop(state):
    for name, record in reversed(list(state.items())):
        if running(record):
            os.kill(record["pid"], signal.SIGTERM)
            for _ in range(100):
                if not running(record):
                    break
                time.sleep(0.1)
            if running(record):
                os.kill(record["pid"], signal.SIGKILL)
        print(f"Stopped {name}")
    STATE.write_text("{}")


def spawn(state, name, command, env):
    with (RUNTIME / f"{name}.log").open("ab") as log:
        process = subprocess.Popen(
            command,
            env=env,
            cwd=ROOT,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    state[name] = {"pid": process.pid, "identity": identity(process.pid)}
    STATE.write_text(json.dumps(state))
    return process


def wait_http(port, process):
    for _ in range(300):
        if process.poll() is not None:
            raise RuntimeError(f"Service on {port} exited; inspect {RUNTIME}/*.log")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service on {port} did not become ready")


def start(binary):
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    state = load_state()
    if any(running(record) for record in state.values()):
        raise RuntimeError("Stack is already running; use status or stop before starting")
    # Never reuse an unknown listener or connect this launcher to another stack.
    for port in (4222, 8222, 8000, 8001, 8002, 8003, 8004):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    source = binary or shutil.which("nats-server") or "/tmp/agentops-nats-bin/nats-server"
    bundled = RUNTIME / "nats-server"
    if not bundled.exists():
        shutil.copy2(source, bundled)
        bundled.chmod(0o700)
    database = RUNTIME / "development.db"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    database.chmod(0o600)
    env = dict(os.environ)
    env.update(
        DATABASE_URL=f"sqlite+aiosqlite:///{database}",
        NATS_URL="nats://127.0.0.1:4222",
        CB_URL="http://127.0.0.1:8001",
        CHAOS_URL="http://127.0.0.1:8002",
        SLO_URL="http://127.0.0.1:8000",
        GATEWAY_URL="http://127.0.0.1:8004",
        GATEWAY_PUBLIC_URL="http://localhost:8004",
        RATE_LIMIT_RPM="120",
        AGENTOPS_ENGINE="py",
        SLO_EVALUATION_INTERVAL_SECONDS="5",
        OTEL_EXPORTER_ENDPOINT="http://127.0.0.1:8000/v1/traces",
    )
    state = {}
    try:
        broker = spawn(
            state,
            "nats",
            [
                str(bundled),
                "-js",
                "-sd",
                str(RUNTIME / "nats-data"),
                "-a",
                "127.0.0.1",
                "-p",
                "4222",
                "-m",
                "8222",
            ],
            env,
        )
        for _ in range(100):
            if broker.poll() is not None:
                raise RuntimeError("NATS exited; inspect nats.log")
            try:
                if httpx.get("http://127.0.0.1:8222/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("NATS did not become ready")
        for name, (module, port) in SERVICES.items():
            if name == "dashboard":
                key_file = RUNTIME / "api-key"
                if key_file.exists():
                    key = key_file.read_text().strip()
                    httpx.get(
                        "http://127.0.0.1:8000/api/v1/tenants/me",
                        headers={"X-API-Key": key},
                        timeout=5,
                    ).raise_for_status()
                else:
                    response = httpx.post(
                        "http://127.0.0.1:8000/api/v1/tenants",
                        json={"slug": "local-dev", "name": "Local development"},
                        timeout=5,
                    )
                    response.raise_for_status()
                    key = response.json()["api_key"]
                    fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, "w") as handle:
                        handle.write(key + "\n")
                env["API_KEY"] = key
            process = spawn(
                state,
                name,
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    f"{module}.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                env,
            )
            wait_http(port, process)
            print(f"Ready {name}: http://localhost:{port}", flush=True)
        print(f"Dashboard login: any username; password stored in {RUNTIME / 'api-key'}")
    except BaseException:
        stop(state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--nats-server")
    args = parser.parse_args()
    if args.action == "start":
        start(args.nats_server)
    elif args.action == "stop":
        RUNTIME.mkdir(mode=0o700, exist_ok=True)
        stop(load_state())
    else:
        state = load_state()
        for name, record in state.items():
            print(f"{name}: {'running' if running(record) else 'stopped'}")
        if not state:
            print("Stack is stopped")


if __name__ == "__main__":
    main()
