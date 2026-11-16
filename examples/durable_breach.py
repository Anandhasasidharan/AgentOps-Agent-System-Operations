"""Verify JetStream retry, offline delivery, and broker restart with real SQLite.

Install packages with make setup. Set NATS_SERVER_BINARY to a local nats-server.
The script binds localhost only, uses temporary storage, and cleans up processes.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import uuid
from functools import partial

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agentops_events import ensure_breach_stream, make_event, publish_event, subscribe_breaches
from circuit_breaker.api import handle_slo_breach
from circuit_breaker.models import Base, EnforcementReceipt


async def main():
    import nats

    binary = os.environ["NATS_SERVER_BINARY"]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"nats://127.0.0.1:{port}"
    clients = []
    process = None
    with tempfile.TemporaryDirectory(prefix="agentops-durable-") as directory:
        engine = create_async_engine(f"sqlite+aiosqlite:///{directory}/test.db")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        with (Path(directory) / "nats.log").open("w+") as log:

            def start():
                return subprocess.Popen(
                    [binary, "-js", "-sd", f"{directory}/nats", "-a", "127.0.0.1", "-p", str(port)],
                    stdout=log,
                    stderr=log,
                )

            async def connect():
                for _ in range(100):
                    try:
                        client = await nats.connect(url, connect_timeout=0.2, allow_reconnect=False)
                        clients.append(client)
                        return client
                    except OSError:
                        await asyncio.sleep(0.1)
                raise RuntimeError("NATS failed to start")

            async def wait_receipts(count):
                for _ in range(100):
                    async with factory() as session:
                        receipts = list(
                            (await session.execute(select(EnforcementReceipt))).scalars()
                        )
                    if len(receipts) == count:
                        return
                    await asyncio.sleep(0.1)
                raise RuntimeError(f"Expected {count} committed enforcement receipts")

            async def wait_ack(client):
                for _ in range(100):
                    info = await client.jetstream().consumer_info(
                        "AGENTOPS_BREACHES", "cb-lockdown"
                    )
                    if info.num_ack_pending == 0 and info.num_pending == 0:
                        return
                    await asyncio.sleep(0.1)
                raise RuntimeError("Enforcement was not acknowledged")

            try:
                process = start()
                publisher = await connect()
                await ensure_breach_stream(publisher)
                tenant = uuid.uuid4()
                first = make_event(
                    "slo", "agentops.slo.breach.7d", tenant, {"agent_id": "first-agent"}
                )
                # No consumer exists yet: this must be retained, not lost.
                await publish_event(publisher, first)
                subscriber = await connect()
                attempts = 0

                async def transient_failure(message):
                    nonlocal attempts
                    attempts += 1
                    if attempts == 1:
                        raise RuntimeError("simulated temporary database failure")
                    await handle_slo_breach(message, session_factory=factory)

                await subscribe_breaches(subscriber, transient_failure)
                await wait_receipts(1)
                await wait_ack(subscriber)
                if attempts != 2:
                    raise RuntimeError(f"Expected a redelivery, got {attempts} attempts")
                print("PASS: offline event retained; failed enforcement retried and committed")
                await subscriber.close()
                second = make_event(
                    "slo", "agentops.slo.breach.7d", tenant, {"agent_id": "second-agent"}
                )
                await publish_event(publisher, second)
                await publisher.close()
                process.terminate()
                process.wait(timeout=10)
                process = start()
                subscriber = await connect()
                await subscribe_breaches(
                    subscriber, partial(handle_slo_breach, session_factory=factory)
                )
                await wait_receipts(2)
                await wait_ack(subscriber)
                print("PASS: broker and subscriber restart recovered the queued breach")
            finally:
                for client in clients:
                    await client.close()
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
