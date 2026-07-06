from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import datetime

import httpx
from agentops_events import AgentOpsEvent, create_nats_client
from agentops_events.models import ALL_TOPICS
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest

from .config import Settings
from .metrics import (
    events_buffer_size,
    events_dropped_total,
    events_published_total,
    ws_connections,
)

logger = logging.getLogger(__name__)

settings = Settings()
app = FastAPI(title="AgentOps Gateway")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

nats_conn = None
event_buffer: deque[dict] = deque(maxlen=settings.event_buffer_size)
ws_clients: set[WebSocket] = set()


async def _validate_key(api_key: str) -> bool:
    slo_url = settings.slo_url.rstrip("/")
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{slo_url}/api/v1/tenants/me", headers={"X-API-Key": api_key})
            return r.status_code == 200
    except Exception:
        return False


async def broadcast(event: AgentOpsEvent):
    data = json.loads(event.model_dump_json())
    event_buffer.append(data)
    events_buffer_size.set(len(event_buffer))
    dead: list[WebSocket] = []
    for ws in ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.discard(ws)
    if dead:
        events_dropped_total.labels(reason="dead_client", service="gateway").inc(len(dead))
    ws_connections.set(len(ws_clients))
    events_published_total.labels(event_type=event.event_type).inc()


async def nats_handler(msg):
    try:
        data = json.loads(msg.data.decode())
        event = AgentOpsEvent(**data)
        await broadcast(event)
    except Exception:
        logger.exception("error handling NATS message")
        events_dropped_total.labels(reason="parse_failed", service="gateway").inc()


async def listen_nats():
    global nats_conn
    nc = await create_nats_client(settings.nats_url)
    if nc is None:
        logger.warning("gateway running without NATS — no real-time events")
        return
    nats_conn = nc
    for topic in ALL_TOPICS:
        await nc.subscribe(topic, cb=nats_handler)
        logger.info("subscribed to %s", topic)


@app.on_event("startup")
async def startup():
    asyncio.ensure_future(listen_nats())


@app.on_event("shutdown")
async def shutdown():
    if nats_conn:
        await nats_conn.close()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "nats_connected": nats_conn is not None and nats_conn.is_connected,
        "ws_clients": len(ws_clients),
        "buffered_events": len(event_buffer),
    }


@app.get("/metrics")
async def metrics():
    return generate_latest()


@app.get("/api/v1/events")
async def get_events(since: str | None = None, x_api_key: str | None = None):
    if x_api_key and not await _validate_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return JSONResponse(
                {"error": "invalid since format, use ISO 8601"}, status_code=400
            )
        result = [e for e in event_buffer if e["timestamp"] >= since_dt.isoformat()]
    else:
        result = list(event_buffer)
    return result


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, api_key: str | None = None):
    if api_key and not await _validate_key(api_key):
        await ws.close(code=4001)
        return
    await ws.accept()
    ws_clients.add(ws)
    ws_connections.set(len(ws_clients))
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)
        ws_connections.set(len(ws_clients))
